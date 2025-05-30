import os
from celery import Celery

celery_app = Celery(
    "storytime_worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

# celery_app.conf.task_routes = {
#     "storytime.worker.tasks.*": {"queue": "default"}
# }

# Import tasks to ensure they are registered with the Celery app
from . import tasks  # noqa: F401,E402 