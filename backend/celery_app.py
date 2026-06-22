from celery import Celery
from backend.core.config import settings

celery_app = Celery(
    "devops_swarm",
    broker  = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",
    backend = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2"
)

celery_app.conf.update(
    task_serializer        = "json",
    accept_content         = ["json"],
    result_serializer      = "json",
    timezone               = "Asia/Kolkata",
    enable_utc             = False,
    task_track_started     = True,
    task_acks_late         = True,
    worker_prefetch_multiplier = 1,
    task_routes = {
        "backend.tasks.run_deployment_pipeline": {
            "queue": "deployments"
        }
    }
)