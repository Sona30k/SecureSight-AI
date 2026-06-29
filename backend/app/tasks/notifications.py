from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def deliver_notification(self, notification_id: str) -> dict:
    """Provider adapter hook for SMS, email, push and WhatsApp gateways."""
    return {"notification_id": notification_id, "status": "sent"}
