import asyncio
import logging

from storytime.database import AsyncSessionLocal
from storytime.infrastructure.spaces import SpacesClient
from storytime.services.job_processor import JobProcessor

from .celery_app import celery_app


@celery_app.task(
    name="storytime.worker.tasks.process_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
)
def process_job(self, job_id):
    """New unified job processing task."""
    logging.info(f"[Celery] process_job called for job_id={job_id}")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_process_job_async(self, job_id))
    return f"Job completed: {job_id}"


async def _process_job_async(self, job_id):
    """Async implementation of job processing."""
    async with AsyncSessionLocal() as session:
        try:
            # Create job processor
            spaces_client = SpacesClient()
            job_processor = JobProcessor(db_session=session, spaces_client=spaces_client)

            # Process the job
            result = await job_processor.process_job(job_id)
            logging.info(f"[Celery] Job {job_id} completed successfully")
            return result

        except Exception as e:
            logging.error(f"[Celery] Job {job_id} failed: {e!s}", exc_info=True)
            raise  # Let Celery handle retry
