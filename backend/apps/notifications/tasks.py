from datetime import timedelta

from celery import shared_task

from apps.notifications.models import Notification
from apps.notifications.services import dispatch_due
from common.time import now


@shared_task
def dispatch_due_reminders() -> int:
    return dispatch_due()


@shared_task
def purge_old_notifications() -> int:
    deleted, _ = Notification.objects.filter(created_at__lt=now() - timedelta(days=90)).delete()
    return deleted
