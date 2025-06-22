import logging

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.database import Job

logger = logging.getLogger(__name__)


async def get_user_job(job_id: str, user_id: str, db: AsyncSession) -> Job:
    """Return the job if it belongs to the user or raise HTTPException."""
    result = await db.execute(select(Job).where(and_(Job.id == job_id, Job.user_id == user_id)))
    job = result.scalar_one_or_none()

    if not job:
        logger.info("Job %s not found or access denied for user %s", job_id, user_id)
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or access denied")

    return job
