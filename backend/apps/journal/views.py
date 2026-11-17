"""HTTP layer of the journal (SDD §7.2)."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from django.db.models import Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Category, Tag, User
from apps.journal import services
from apps.journal.models import TEMPLATES, EntryType, JournalEntry
from apps.schedule.serializers import OwnedPK
from common.exceptions import NotFoundError
from common.idempotency import idempotent
from common.pagination import PageNumberPagination

# ---------------------------------------------------------------- selectors (read side)


def entry_list(
    user: User,
    *,
    first: date | None = None,
    last: date | None = None,
    entry_type: str | None = None,
    tag: UUID | None = None,
    q: str = "",
) -> QuerySet[JournalEntry]:
    qs = JournalEntry.objects.filter(user=user).prefetch_related("tags")
    if first:
        qs = qs.filter(entry_date__gte=first)
    if last:
        qs = qs.filter(entry_date__lte=last)
    if entry_type:
        qs = qs.filter(entry_type=entry_type)
    if tag:
        qs = qs.filter(tags__id=tag)
    if q:
        # Portable search; PostgreSQL FTS (ADR-018) replaces it once the GIN index is added.
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q) | Q(sections__icontains=q))
    return qs.distinct()


def entry_get(user: User, entry_id: UUID | str) -> JournalEntry:
    try:
        return JournalEntry.objects.prefetch_related("tags").get(user=user, id=entry_id)
    except (JournalEntry.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


# ---------------------------------------------------------------- serializers


class EntrySerializer(serializers.ModelSerializer):
    category_id = serializers.UUIDField(read_only=True, allow_null=True)
    tag_ids = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "entry_date",
            "entry_type",
            "title",
            "template_key",
            "sections",
            "body",
            "category_id",
            "tag_ids",
            "is_sensitive",
            "ai_allowed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_tag_ids(self, obj: JournalEntry) -> list[str]:
        return [str(t.id) for t in obj.tags.all()]


class EntryWriteSerializer(serializers.Serializer):
    entry_date = serializers.DateField(required=False)
    entry_type = serializers.ChoiceField(choices=EntryType.choices, default=EntryType.FREE)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    sections = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)
    body = serializers.CharField(required=False, allow_blank=True, max_length=100_000)
    category_id = OwnedPK(Category, source="category")
    tag_ids = OwnedPK(Tag, source="tags", many=True, allow_null=False, required=False)
    is_sensitive = serializers.BooleanField(required=False)
    ai_allowed = serializers.BooleanField(required=False)


class ListQuery(serializers.Serializer):
    from_ = serializers.DateField(required=False)
    to = serializers.DateField(required=False)
    type = serializers.ChoiceField(choices=EntryType.choices, required=False)
    tag = serializers.UUIDField(required=False)
    q = serializers.CharField(required=False, max_length=200)

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        return fields


def _input(cls: type[serializers.Serializer], request: Request, **kw: Any) -> dict[str, Any]:
    s = cls(data=request.data, context={"request": request}, **kw)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


def _out(request: Request, entry_id: Any, code: int = 200) -> Response:
    return Response(EntrySerializer(entry_get(request.user, entry_id)).data, status=code)


class JournalListView(APIView):
    @extend_schema(
        parameters=[ListQuery], responses={200: EntrySerializer(many=True)}, operation_id="journal_list"
    )
    def get(self, request: Request) -> Response:
        q = ListQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        d = q.validated_data
        qs = entry_list(
            request.user,
            first=d.get("from"),
            last=d.get("to"),
            entry_type=d.get("type"),
            tag=d.get("tag"),
            q=(d.get("q") or "").strip(),
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(EntrySerializer(page, many=True).data)

    @extend_schema(request=EntryWriteSerializer, responses={201: EntrySerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        entry = services.entry_create(user=request.user, data=_input(EntryWriteSerializer, request))
        return _out(request, entry.id, status.HTTP_201_CREATED)


class JournalDetailView(APIView):
    @extend_schema(responses={200: EntrySerializer})
    def get(self, request: Request, entry_id: str) -> Response:
        return _out(request, entry_id)

    @extend_schema(request=EntryWriteSerializer, responses={200: EntrySerializer})
    def patch(self, request: Request, entry_id: str) -> Response:
        entry = entry_get(request.user, entry_id)
        data = _input(EntryWriteSerializer, request, partial=True)
        services.entry_update(user=request.user, entry=entry, data=data)
        return _out(request, entry_id)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, entry_id: str) -> Response:
        services.entry_delete(user=request.user, entry=entry_get(request.user, entry_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class JournalByDateView(APIView):
    """The daily reflection of a date, or 404 when it has not been written yet."""

    @extend_schema(responses={200: EntrySerializer})
    def get(self, request: Request, day: str) -> Response:
        try:
            parsed = date.fromisoformat(day)
        except ValueError as exc:
            raise NotFoundError() from exc
        entry = entry_list(request.user, first=parsed, last=parsed, entry_type=EntryType.DAILY).first()
        if entry is None:
            raise NotFoundError("No daily reflection for this date.")
        return Response(EntrySerializer(entry).data)


class JournalTemplatesView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request: Request) -> Response:
        return Response({"results": [{"key": k, "sections": list(v)} for k, v in TEMPLATES.items()]})
