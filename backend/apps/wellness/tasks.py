from celery import shared_task

from apps.accounts.models import User
from apps.wellness.services import overload_check


@shared_task
def overload_check_all() -> int:
    """At most one observation per user every 3 days (SDD §5.9)."""
    sent = 0
    for user in User.objects.filter(is_active=True).select_related("profile"):
        sent += int(overload_check(user))
    return sent
