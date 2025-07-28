import logging
import os

from celery import Celery
from celery.signals import (
    after_setup_logger,
    after_setup_task_logger,
    task_failure,
    worker_ready,
    worker_shutting_down,
)

from . import celery_config

# Set up base logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

celery_app = Celery(
    "storytime_worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

# Load configuration from celery_config module
celery_app.config_from_object(celery_config)

# Additional inline configuration
celery_app.conf.update(
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    worker_log_color=False,
    worker_hijack_root_logger=False,
    task_default_retry_delay=60,
    task_max_retries=3,
)


@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    """Configure Celery logger."""
    formatter = logging.Formatter("[%(asctime)s: %(levelname)s/%(processName)s] %(message)s")

    # Add file handler for persistent logs
    file_handler = logging.FileHandler("/tmp/celery_worker.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


@after_setup_task_logger.connect
def setup_task_logger(logger, *args, **kwargs):
    """Configure task logger."""
    formatter = logging.Formatter(
        "[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s"
    )

    # Add file handler for persistent logs
    file_handler = logging.FileHandler("/tmp/celery_tasks.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


@task_failure.connect
def handle_task_failure(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    traceback=None,
    einfo=None,
    **kw,
):
    """Log detailed information when a task fails."""
    logger.error(f"Task {sender.name}[{task_id}] failed with exception: {exception}")
    logger.error(f"Task args: {args}")
    logger.error(f"Task kwargs: {kwargs}")
    if einfo:
        logger.error(f"Exception info: {einfo}")


@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Log when worker is ready."""
    logger.info(f"Worker ready: {sender}")
    logger.info(
        f"Worker configuration: concurrency={celery_app.conf.worker_concurrency}, "
        f"max_tasks_per_child={celery_app.conf.worker_max_tasks_per_child}, "
        f"max_memory_per_child={celery_app.conf.worker_max_memory_per_child}"
    )


@worker_shutting_down.connect
def worker_shutting_down_handler(sig, how, exitcode, **kwargs):
    """Log when worker is shutting down."""
    logger.warning(f"Worker shutting down: signal={sig}, how={how}, exitcode={exitcode}")


# Import tasks to ensure they are registered with the Celery app
from . import tasks  # noqa: F401,E402
