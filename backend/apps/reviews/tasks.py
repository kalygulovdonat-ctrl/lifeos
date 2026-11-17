from datetime import timedelta

from celery import shared_task

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import notification_create
from apps.reviews.models import ReviewStatus, WeeklyReview
from apps.reviews.services import week_of
from common.time import local_now, now

REMIND_HOUR = 18


@shared_task
def remind_weekly_review() -> int:
    """On the last day of the user's week, after 18:00 local, if the week has no completed review."""
    sent = 0
    for user in User.objects.filter(is_active=True).select_related("profile"):
        local = local_now(user.profile.timezone)
        first, last = week_of(user, local.date())
        if local.date() != last or local.hour < REMIND_HOUR:
            continue
        if WeeklyReview.objects.filter(user=user, week_start=first, status=ReviewStatus.COMPLETED).exists():
            continue
        if Notification.objects.filter(
            user=user, type="REVIEW_DUE", created_at__gte=now() - timedelta(days=1)
        ).exists():
            continue
        notification_create(user=user, type="REVIEW_DUE", message_key="reviewDue", link="/reviews")
        sent += 1
    return sent
