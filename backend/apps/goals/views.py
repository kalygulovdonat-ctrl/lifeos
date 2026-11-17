"""HTTP layer of goals (SDD §7.2)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Category
from apps.goals import selectors, services
from apps.goals.models import (
    Goal,
    GoalLevel,
    GoalProgress,
    GoalStatus,
    GoalStatusChange,
    Milestone,
    MilestoneStatus,
    ProgressType,
)
from apps.schedule.serializers import OwnedPK
from apps.tasks import selectors as task_selectors
from apps.tasks.serializers import TaskSerializer
from common.idempotency import idempotent

DECIMAL = {"max_digits": 12, "decimal_places": 2}


class GoalWriteSerializer(serializers.Serializer):
    parent_id = OwnedPK(Goal, source="parent")
    level = serializers.ChoiceField(choices=GoalLevel.choices, required=False)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    category_id = OwnedPK(Category, source="category")
    start_date = serializers.DateField(required=False)
    target_date = serializers.DateField(required=False, allow_null=True)
    progress_type = serializers.ChoiceField(choices=ProgressType.choices, required=False)
    metric_unit = serializers.CharField(max_length=20, required=False, allow_blank=True)
    start_value = serializers.DecimalField(**DECIMAL, required=False, allow_null=True)
    target_value = serializers.DecimalField(**DECIMAL, required=False, allow_null=True)
    current_value = serializers.DecimalField(**DECIMAL, required=False, allow_null=True)


class MilestoneSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=MilestoneStatus.choices, required=False)
    weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, min_value=Decimal("0.01")
    )

    class Meta:
        model = Milestone
        fields = ["id", "title", "due_date", "status", "weight", "completed_at", "sort_order"]
        read_only_fields = ["id", "completed_at"]


class GoalSerializer(serializers.ModelSerializer):
    parent_id = serializers.UUIDField(read_only=True, allow_null=True)
    category_id = serializers.UUIDField(read_only=True, allow_null=True)
    milestones_total = serializers.IntegerField(read_only=True, default=0)
    milestones_done = serializers.IntegerField(read_only=True, default=0)
    tasks_total = serializers.IntegerField(read_only=True, default=0)
    tasks_done = serializers.IntegerField(read_only=True, default=0)
    target_reached = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = [
            "id",
            "parent_id",
            "level",
            "title",
            "description",
            "category_id",
            "status",
            "start_date",
            "target_date",
            "progress_type",
            "metric_unit",
            "start_value",
            "target_value",
            "current_value",
            "progress_pct",
            "target_reached",
            "completed_at",
            "is_archived",
            "milestones_total",
            "milestones_done",
            "tasks_total",
            "tasks_done",
            "created_at",
        ]
        read_only_fields = fields

    def get_target_reached(self, obj: Goal) -> bool:
        """100% does not complete the goal by itself: the UI asks the user to confirm (BR-045)."""
        return obj.progress_pct >= 100 and obj.status == GoalStatus.ACTIVE


class GoalDetailSerializer(GoalSerializer):
    milestones = MilestoneSerializer(many=True, read_only=True)

    class Meta(GoalSerializer.Meta):
        fields = [*GoalSerializer.Meta.fields, "milestones"]
        read_only_fields = fields


def _input(cls: type[serializers.Serializer], request: Request, **kw: Any) -> dict[str, Any]:
    s = cls(data=request.data, context={"request": request}, **kw)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


def _detail(request: Request, goal_id: Any, code: int = 200) -> Response:
    return Response(GoalDetailSerializer(selectors.goal_get(request.user, goal_id)).data, status=code)


class GoalListQuery(serializers.Serializer):
    status = serializers.CharField(required=False)
    level = serializers.ChoiceField(choices=GoalLevel.choices, required=False)
    tree = serializers.BooleanField(required=False, default=False)
    archived = serializers.BooleanField(required=False, default=False)


def _tree(nodes: list) -> list[dict[str, Any]]:
    return [{**GoalSerializer(g).data, "children": _tree(children)} for g, children in nodes]


class GoalListView(APIView):
    @extend_schema(
        parameters=[GoalListQuery], responses={200: GoalSerializer(many=True)}, operation_id="goals_list"
    )
    def get(self, request: Request) -> Response:
        q = GoalListQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        d = q.validated_data
        statuses = [s for s in (d.get("status") or "").split(",") if s]
        if bad := [s for s in statuses if s not in GoalStatus.values]:
            raise serializers.ValidationError({"status": [f"Unknown value(s): {', '.join(bad)}."]})
        goals = list(
            selectors.goal_list(request.user, statuses=statuses, level=d.get("level"), archived=d["archived"])
        )
        if d["tree"]:
            return Response({"results": _tree(selectors.build_tree(goals))})
        return Response({"results": GoalSerializer(goals, many=True).data})

    @extend_schema(request=GoalWriteSerializer, responses={201: GoalDetailSerializer})
    @idempotent
    def post(self, request: Request) -> Response:
        goal = services.goal_create(user=request.user, data=_input(GoalWriteSerializer, request))
        return _detail(request, goal.id, status.HTTP_201_CREATED)


class GoalDetailView(APIView):
    @extend_schema(responses={200: GoalDetailSerializer})
    def get(self, request: Request, goal_id: str) -> Response:
        return _detail(request, goal_id)

    @extend_schema(request=GoalWriteSerializer, responses={200: GoalDetailSerializer})
    def patch(self, request: Request, goal_id: str) -> Response:
        goal = selectors.goal_get(request.user, goal_id)
        services.goal_update(
            user=request.user, goal=goal, data=_input(GoalWriteSerializer, request, partial=True)
        )
        return _detail(request, goal_id)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, goal_id: str) -> Response:
        services.goal_delete(user=request.user, goal=selectors.goal_get(request.user, goal_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class StatusActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=list(services.ACTIONS))
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class GoalStatusView(APIView):
    @extend_schema(request=StatusActionSerializer, responses={200: GoalDetailSerializer})
    def post(self, request: Request, goal_id: str) -> Response:
        goal = selectors.goal_get(request.user, goal_id)
        services.goal_change_status(user=request.user, goal=goal, **_input(StatusActionSerializer, request))
        return _detail(request, goal_id)


class ProgressInputSerializer(serializers.Serializer):
    value = serializers.DecimalField(**DECIMAL)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class GoalProgressView(APIView):
    @extend_schema(request=ProgressInputSerializer, responses={200: GoalDetailSerializer})
    def post(self, request: Request, goal_id: str) -> Response:
        goal = selectors.goal_get(request.user, goal_id)
        services.goal_set_progress(user=request.user, goal=goal, **_input(ProgressInputSerializer, request))
        return _detail(request, goal_id)


class ProgressRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalProgress
        fields = ["id", "recorded_at", "value", "progress_pct", "source", "note"]


class StatusRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalStatusChange
        fields = ["id", "from_status", "to_status", "reason", "changed_at"]


class GoalHistoryView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request: Request, goal_id: str) -> Response:
        goal = selectors.goal_get(request.user, goal_id)
        return Response(
            {
                "progress": ProgressRowSerializer(
                    selectors.progress_history(request.user, goal), many=True
                ).data,
                "status": StatusRowSerializer(selectors.status_history(request.user, goal), many=True).data,
            }
        )


class GoalTasksView(APIView):
    @extend_schema(responses={200: TaskSerializer(many=True)})
    def get(self, request: Request, goal_id: str) -> Response:
        goal = selectors.goal_get(request.user, goal_id)
        ids = [link.task_id for link in selectors.linked_tasks(request.user, goal)]
        tasks = task_selectors.task_list(request.user).filter(id__in=ids)
        ctx = {"request": request, "tz": request.user.profile.timezone}
        return Response({"results": TaskSerializer(tasks, many=True, context=ctx).data})


class GoalTaskLinkView(APIView):
    @extend_schema(request=None, responses={200: GoalDetailSerializer})
    def post(self, request: Request, goal_id: str, task_id: str) -> Response:
        goal = selectors.goal_get(request.user, goal_id)
        task = task_selectors.task_get(request.user, task_id)
        services.goal_link_task(user=request.user, goal=goal, task=task)
        return _detail(request, goal_id)

    @extend_schema(responses={200: GoalDetailSerializer})
    def delete(self, request: Request, goal_id: str, task_id: str) -> Response:
        goal = selectors.goal_get(request.user, goal_id)
        task = task_selectors.task_get(request.user, task_id)
        services.goal_unlink_task(user=request.user, goal=goal, task=task)
        return _detail(request, goal_id)


class MilestoneListView(APIView):
    @extend_schema(request=MilestoneSerializer, responses={201: MilestoneSerializer})
    def post(self, request: Request, goal_id: str) -> Response:
        goal = selectors.goal_get(request.user, goal_id)
        m = services.milestone_create(user=request.user, goal=goal, data=_input(MilestoneSerializer, request))
        return Response(MilestoneSerializer(m).data, status=status.HTTP_201_CREATED)


class MilestoneDetailView(APIView):
    @extend_schema(request=MilestoneSerializer, responses={200: MilestoneSerializer})
    def patch(self, request: Request, milestone_id: str) -> Response:
        m = selectors.milestone_get(request.user, milestone_id)
        data = _input(MilestoneSerializer, request, partial=True)
        return Response(
            MilestoneSerializer(services.milestone_update(user=request.user, milestone=m, data=data)).data
        )

    @extend_schema(responses={204: None})
    def delete(self, request: Request, milestone_id: str) -> Response:
        services.milestone_delete(
            user=request.user, milestone=selectors.milestone_get(request.user, milestone_id)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MilestoneCompleteView(APIView):
    @extend_schema(request=None, responses={200: MilestoneSerializer})
    def post(self, request: Request, milestone_id: str) -> Response:
        m = selectors.milestone_get(request.user, milestone_id)
        return Response(MilestoneSerializer(services.milestone_complete(user=request.user, milestone=m)).data)
