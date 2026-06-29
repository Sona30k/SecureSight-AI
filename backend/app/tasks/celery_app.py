from celery import Celery

from app.config.settings import settings

celery_app = Celery("sentinelx", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json", result_serializer="json", accept_content=["json"],
    timezone="UTC", enable_utc=True, task_track_started=True,
    task_routes={"app.tasks.*": {"queue": "sentinelx"}},
)
