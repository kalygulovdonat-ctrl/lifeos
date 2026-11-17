"""Weekly Review flow (SDD §4.11, §10.3): DRAFT with a live snapshot → decisions → COMPLETED."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.analytics.selectors import FORMULA_VERSION, summary
from apps.reviews.models import Decision, ReviewStatus, ReviewTaskDecision, WeeklyReview
from apps.tasks import services as task_services
from apps.tasks.models import OPEN_STATUSES, Task, TaskStatus
from common.audit import audit
from common.exceptions import ConflictError, DomainValidationError, NotFoundError
from common.time import local_today, now, period_bounds

TEXT_FIELDS = {"wins", "challenges", "lessons", "next_week_focus", "week_rating"}


def _invalid(field: str, message: str) -> DomainValidationError:
    return DomainValidationError(details={field: [message]})


def _locked() -> ConflictError:
    return ConflictError("This review is already completed.", code="REVIEW_ALREADY_COMPLETED")


def week_of(user: User, day: date) -> tuple[date, date]:
    b = period_bounds(user.profile.timezone, "week", day, user.profile.week_start)
    return b.first_day, b.last_day


def review_get(user: User, review_id: UUID | str) -> WeeklyReview:
    try:
        return WeeklyReview.objects.get(user=user, id=review_id)
    except (WeeklyReview.DoesNotExist, ValueError) as exc:
        raise NotFoundError() from exc


def review_list(user: User) -> QuerySet[WeeklyReview]:
    return WeeklyReview.objects.filter(user=user)


def snapshot(user: User, week_start: date) -> dict[str, Any]:
    data = summary(user, "week", week_start)
    return data


def review_start(*, user: User, week_start: date | None = None) -> WeeklyReview:
    """Idempotent per week: returns the existing review of that week."""
    first, last = week_of(user, week_start or local_today(user.profile.timezone))
    if week_start and week_start != first:
        raise _invalid("week_start", f"The week starts on {first.isoformat()}.")
    existing = WeeklyReview.objects.filter(user=user, week_start=first).first()
    if existing:
        return (
            review_refresh(user=user, review=existing) if existing.status == ReviewStatus.DRAFT else existing
        )
    try:
        with transaction.atomic():
            review = WeeklyReview.objects.create(
                user=user,
                week_start=first,
                week_end=last,
                timezone=user.profile.timezone,
                stats_snapshot=snapshot(user, first),
                formula_version=FORMULA_VERSION,
            )
    except IntegrityError:
        return WeeklyReview.objects.get(user=user, week_start=first)
    audit(user=user, entity_type="weekly_review", entity_id=review.id, action="CREATE")
    return review


def review_refresh(*, user: User, review: WeeklyReview) -> WeeklyReview:
    if review.status == ReviewStatus.COMPLETED:
        raise _locked()
    review.stats_snapshot = snapshot(user, review.week_start)
    review.formula_version = FORMULA_VERSION
    review.save(update_fields=["stats_snapshot", "formula_version", "updated_at"])
    return review


def review_update(*, user: User, review: WeeklyReview, data: dict[str, Any]) -> WeeklyReview:
    if review.status == ReviewStatus.COMPLETED:
        raise _locked()
    for k, v in data.items():
        if k in TEXT_FIELDS:
            setattr(review, k, v.strip() if isinstance(v, str) else v)
    review.save()
    return review


def unfinished_tasks(user: User, review: WeeklyReview) -> QuerySet[Task]:
    """Open tasks that were due by the end of the week or planned inside it."""
    end = period_bounds(review.timezone, "day", review.week_end).end
    start = period_bounds(review.timezone, "day", review.week_start).start
    return (
        Task.objects.filter(user=user, status__in=OPEN_STATUSES, is_archived=False)
        .filter(Q(due_at__lt=end) | Q(scheduled_start__lt=end, scheduled_end__gt=start))
        .order_by("due_at")
    )


@transaction.atomic
def set_decisions(
    *, user: User, review: WeeklyReview, decisions: list[dict[str, Any]]
) -> list[ReviewTaskDecision]:
    if review.status == ReviewStatus.COMPLETED:
        raise _locked()
    allowed = {t.id: t for t in unfinished_tasks(user, review)}
    ReviewTaskDecision.objects.filter(review=review).delete()
    rows = []
    for d in decisions:
        task = d["task"]
        if task.user_id != user.id or task.id not in allowed:
            raise _invalid("task_id", "Only unfinished tasks of this week can be decided.")
        if d["decision"] == Decision.RESCHEDULE and not d.get("new_due_at"):
            raise _invalid("new_due_at", "Rescheduling needs a new date.")
        rows.append(
            ReviewTaskDecision(
                user=user, review=review, task=task, decision=d["decision"], new_due_at=d.get("new_due_at")
            )
        )
    return ReviewTaskDecision.objects.bulk_create(rows)


def _move(user: User, task: Task, due: Any, reason: str) -> None:
    """A new due date: a postponement with history, or a plain date for a backlog task."""
    if task.status == TaskStatus.BACKLOG:
        task_services.task_update(user=user, task=task, data={"due_at": due})
    else:
        task_services.task_change_status(
            user=user, task=task, status=TaskStatus.POSTPONED, new_due_at=due, reason=reason
        )


@transaction.atomic
def review_complete(*, user: User, review: WeeklyReview) -> WeeklyReview:
    """Applies the task decisions through the task services, then freezes the review."""
    review = WeeklyReview.objects.select_for_update().get(pk=review.pk, user=user)
    if review.status == ReviewStatus.COMPLETED:
        raise _locked()
    next_week_end = task_services.end_of_local_day(review.week_end + timedelta(days=7), review.timezone)
    reason = f"Weekly review {review.week_start.isoformat()}"
    for d in ReviewTaskDecision.objects.filter(review=review).select_related("task"):
        task = d.task
        if task.deleted_at is not None or task.status not in OPEN_STATUSES:
            continue
        if d.decision == Decision.CARRY_OVER:
            _move(user, task, next_week_end, reason)
        elif d.decision == Decision.RESCHEDULE:
            _move(user, task, d.new_due_at, reason)
        elif d.decision == Decision.BACKLOG and task.status != TaskStatus.BACKLOG:
            task_services.task_change_status(user=user, task=task, status=TaskStatus.BACKLOG, reason=reason)
        elif d.decision == Decision.CANCEL:
            task_services.task_change_status(user=user, task=task, status=TaskStatus.CANCELLED, reason=reason)
    review.stats_snapshot = snapshot(user, review.week_start)
    review.status = ReviewStatus.COMPLETED
    review.completed_at = now()
    review.save()
    audit(user=user, entity_type="weekly_review", entity_id=review.id, action="COMPLETE")
    return review
