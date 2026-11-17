"""Weekly Review API (SDD §7.2)."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews import services
from apps.reviews.models import Decision, ReviewTaskDecision, WeeklyReview
from apps.schedule.serializers import OwnedPK
from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer
from common.fields import AwareDateTimeField


class DecisionSerializer(serializers.ModelSerializer):
    task_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ReviewTaskDecision
        fields = ["task_id", "decision", "new_due_at"]


class ReviewSerializer(serializers.ModelSerializer):
    decisions = DecisionSerializer(many=True, read_only=True)

    class Meta:
        model = WeeklyReview
        fields = [
            "id",
            "week_start",
            "week_end",
            "status",
            "stats_snapshot",
            "formula_version",
            "wins",
            "challenges",
            "lessons",
            "next_week_focus",
            "week_rating",
            "completed_at",
            "decisions",
            "created_at",
        ]
        read_only_fields = fields


class ReviewListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyReview
        fields = ["id", "week_start", "week_end", "status", "week_rating", "completed_at"]


class ReviewPatchSerializer(serializers.Serializer):
    wins = serializers.CharField(required=False, allow_blank=True, max_length=10_000)
    challenges = serializers.CharField(required=False, allow_blank=True, max_length=10_000)
    lessons = serializers.CharField(required=False, allow_blank=True, max_length=10_000)
    next_week_focus = serializers.CharField(required=False, allow_blank=True, max_length=10_000)
    week_rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=10)


class StartSerializer(serializers.Serializer):
    week_start = serializers.DateField(required=False)


class DecisionInput(serializers.Serializer):
    task_id = OwnedPK(Task, source="task", allow_null=False, required=True)
    decision = serializers.ChoiceField(choices=Decision.choices)
    new_due_at = AwareDateTimeField(required=False, allow_null=True)


class DecisionsSerializer(serializers.Serializer):
    decisions = DecisionInput(many=True)


def _out(review: WeeklyReview, code: int = 200) -> Response:
    review = WeeklyReview.objects.prefetch_related("decisions").get(pk=review.pk)
    return Response(ReviewSerializer(review).data, status=code)


def _input(cls: type[serializers.Serializer], request: Request) -> dict[str, Any]:
    s = cls(data=request.data, context={"request": request})
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


class ReviewListView(APIView):
    @extend_schema(responses={200: ReviewListSerializer(many=True)}, operation_id="reviews_list")
    def get(self, request: Request) -> Response:
        return Response({"results": ReviewListSerializer(services.review_list(request.user), many=True).data})

    @extend_schema(request=StartSerializer, responses={201: ReviewSerializer})
    def post(self, request: Request) -> Response:
        data = _input(StartSerializer, request)
        return _out(services.review_start(user=request.user, week_start=data.get("week_start")), 201)


class ReviewDetailView(APIView):
    @extend_schema(responses={200: ReviewSerializer})
    def get(self, request: Request, review_id: str) -> Response:
        return _out(services.review_get(request.user, review_id))

    @extend_schema(request=ReviewPatchSerializer, responses={200: ReviewSerializer})
    def patch(self, request: Request, review_id: str) -> Response:
        review = services.review_get(request.user, review_id)
        return _out(
            services.review_update(
                user=request.user, review=review, data=_input(ReviewPatchSerializer, request)
            )
        )


class RefreshView(APIView):
    @extend_schema(request=None, responses={200: ReviewSerializer})
    def post(self, request: Request, review_id: str) -> Response:
        review = services.review_get(request.user, review_id)
        return _out(services.review_refresh(user=request.user, review=review))


class UnfinishedView(APIView):
    @extend_schema(responses={200: TaskSerializer(many=True)})
    def get(self, request: Request, review_id: str) -> Response:
        review = services.review_get(request.user, review_id)
        tasks = services.unfinished_tasks(request.user, review)
        ctx = {"request": request, "tz": request.user.profile.timezone}
        return Response({"results": TaskSerializer(tasks, many=True, context=ctx).data})


class DecisionsView(APIView):
    @extend_schema(request=DecisionsSerializer, responses={200: ReviewSerializer})
    def put(self, request: Request, review_id: str) -> Response:
        review = services.review_get(request.user, review_id)
        data = _input(DecisionsSerializer, request)
        services.set_decisions(user=request.user, review=review, decisions=data["decisions"])
        return _out(review)


class CompleteView(APIView):
    @extend_schema(request=None, responses={200: ReviewSerializer})
    def post(self, request: Request, review_id: str) -> Response:
        review = services.review_get(request.user, review_id)
        return _out(services.review_complete(user=request.user, review=review), status.HTTP_200_OK)
