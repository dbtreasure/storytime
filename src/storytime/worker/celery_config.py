"""Celery configuration with enhanced logging and monitoring."""

import os
from datetime import timedelta

# Logging configuration
CELERYD_LOG_LEVEL = os.getenv("CELERY_LOG_LEVEL", "INFO")
CELERYD_LOG_FORMAT = (
    "[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s"
)

# Task configuration
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_SEND_EVENTS = True

# Worker configuration
CELERYD_PREFETCH_MULTIPLIER = 1  # Process one task at a time
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50  # Restart worker after 50 tasks to prevent memory leaks
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 1024 * 1024  # 1GB memory limit

# Task time limits
CELERY_TASK_SOFT_TIME_LIMIT = 3600  # 1 hour soft limit
CELERY_TASK_TIME_LIMIT = 3900  # 1 hour 5 min hard limit

# Result backend configuration
CELERY_RESULT_EXPIRES = timedelta(days=1)
CELERY_RESULT_PERSISTENT = True

# Serialization
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

# Error handling
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True  # Tasks acknowledged after completion

# Beat schedule (if using periodic tasks)
CELERY_BEAT_SCHEDULE = {}

# Additional monitoring
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

# Resource limits
CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "2"))
