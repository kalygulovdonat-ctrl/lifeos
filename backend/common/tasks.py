from celery import shared_task
from django.utils import timezone

from common.idempotency import TTL
from common.models import IdempotencyRecord


@shared_task
def purge_idempotency_records() -> int:
    deleted, _ = IdempotencyRecord.objects.filter(created_at__lt=timezone.now() - TTL).delete()
    return deleted
