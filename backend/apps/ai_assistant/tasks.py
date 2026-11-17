from celery import shared_task


@shared_task(acks_late=True, soft_time_limit=180)
def ai_generate_response(message_id: str) -> str:
    from apps.ai_assistant.services import respond

    return respond(message_id).status


@shared_task
def expire_actions() -> int:
    from apps.ai_assistant.services import expire_stale

    return expire_stale()
