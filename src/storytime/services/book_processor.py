"""Book processor service for handling full book processing jobs."""

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.database import Job, JobStatus, StepStatus
from storytime.infrastructure.spaces import SpacesClient
from storytime.models import JobResponse
from storytime.services.book_analyzer import BookAnalyzer, ChapterInfo
from storytime.services.job_processor import JobProcessor

logger = logging.getLogger(__name__)


class BookProcessor:
    """Processor for book splitting and multi-chapter audio generation."""

    def __init__(
        self,
        db_session: AsyncSession,
        spaces_client: SpacesClient,
        job_processor: JobProcessor | None = None,
    ):
        self.db_session = db_session
        self.spaces_client = spaces_client
        self.job_processor = job_processor or JobProcessor(db_session, spaces_client)
        self.book_analyzer = BookAnalyzer()

    async def process_book_job(self, job_id: str) -> JobResponse:
        """Process a book splitting job."""
        logger.info(f"Starting book processing job {job_id}")

        # Get job from database
        job = await self.job_processor._get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Update job status to processing
        await self.job_processor._update_job_status(
            job_id, JobStatus.PROCESSING, started_at=datetime.utcnow()
        )

        try:
            # Execute book processing workflow
            result = await self._execute_book_workflow(job)

            # Update job as completed
            await self.job_processor._update_job_status(
                job_id,
                JobStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.utcnow(),
                result_data=result,
            )

            logger.info(f"Book job {job_id} completed successfully")
            return await self.job_processor._get_job_response(job_id)

        except Exception as e:
            logger.error(f"Book job {job_id} failed: {e!s}", exc_info=True)
            await self.job_processor._update_job_status(
                job_id, JobStatus.FAILED, error_message=str(e), completed_at=datetime.utcnow()
            )
            raise

    async def _execute_book_workflow(self, job: Job) -> dict[str, Any]:
        """Execute the book processing workflow with steps."""

        # Step 1: Load book text
        load_step = await self.job_processor._create_job_step(
            job.id, "load_book", 0, "Load book text from storage"
        )
        await self.job_processor._update_job_step(
            load_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
        )

        try:
            book_text = await self._load_book_text(job)
            await self.job_processor._update_job_step(
                load_step.id, StepStatus.COMPLETED, progress=1.0, completed_at=datetime.utcnow()
            )
        except Exception as e:
            await self.job_processor._update_job_step(
                load_step.id,
                StepStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

        # Step 2: Analyze book structure
        analyze_step = await self.job_processor._create_job_step(
            job.id, "analyze_structure", 1, "Analyze book structure and detect chapters"
        )
        await self.job_processor._update_job_step(
            analyze_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
        )

        try:
            chapters = self.book_analyzer.analyze_book(book_text)
            await self.job_processor._update_job_step(
                analyze_step.id,
                StepStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.utcnow(),
                step_metadata={"chapter_count": len(chapters)},
            )
        except Exception as e:
            await self.job_processor._update_job_step(
                analyze_step.id,
                StepStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

        # Step 3: Split and save chapters
        split_step = await self.job_processor._create_job_step(
            job.id, "split_chapters", 2, "Split book into individual chapters"
        )
        await self.job_processor._update_job_step(
            split_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
        )

        try:
            chapter_files = await self._split_and_save_chapters(job.id, book_text, chapters)
            await self.job_processor._update_job_step(
                split_step.id, StepStatus.COMPLETED, progress=1.0, completed_at=datetime.utcnow()
            )
        except Exception as e:
            await self.job_processor._update_job_step(
                split_step.id,
                StepStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

        # Step 4: Create child jobs for each chapter
        create_jobs_step = await self.job_processor._create_job_step(
            job.id, "create_chapter_jobs", 3, "Create processing jobs for each chapter"
        )
        await self.job_processor._update_job_step(
            create_jobs_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
        )

        try:
            child_job_ids = await self._create_chapter_jobs(job, chapters, chapter_files)
            await self.job_processor._update_job_step(
                create_jobs_step.id,
                StepStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.utcnow(),
                step_metadata={"child_job_ids": child_job_ids},
            )
        except Exception as e:
            await self.job_processor._update_job_step(
                create_jobs_step.id,
                StepStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

        # Update overall progress
        await self.job_processor._update_job_status(job.id, JobStatus.PROCESSING, progress=1.0)

        return {
            "processing_type": "book_splitting",
            "chapter_count": len(chapters),
            "child_job_ids": child_job_ids,
            "chapter_files": chapter_files,
            "total_word_count": len(book_text.split()),
        }

    async def _load_book_text(self, job: Job) -> str:
        """Load book text from storage or job config."""
        if job.config and job.config.get("content"):
            return job.config["content"]
        elif job.input_file_key:
            return await self.spaces_client.download_text_file(job.input_file_key)
        else:
            raise ValueError("No book content or file provided")

    async def _split_and_save_chapters(
        self, job_id: str, book_text: str, chapters: list[ChapterInfo]
    ) -> list[dict[str, Any]]:
        """Split book into chapters and save to storage."""
        chapter_files = []

        for i, chapter in enumerate(chapters):
            # Extract chapter text
            chapter_text = book_text[chapter.start_position : chapter.end_position]

            # Generate file key
            chapter_number = chapter.chapter_number or (i + 1)
            file_key = f"jobs/{job_id}/chapters/chapter_{chapter_number:03d}.txt"

            # Upload to storage
            await self.spaces_client.upload_text_file(file_key, chapter_text)

            chapter_files.append(
                {
                    "chapter_number": chapter_number,
                    "title": chapter.title,
                    "file_key": file_key,
                    "word_count": chapter.word_count,
                    "is_special": chapter.is_special,
                }
            )

            logger.info(
                f"Saved chapter {chapter_number}: '{chapter.title}' "
                f"({chapter.word_count} words) to {file_key}"
            )

        return chapter_files

    async def _create_chapter_jobs(
        self, parent_job: Job, chapters: list[ChapterInfo], chapter_files: list[dict[str, Any]]
    ) -> list[str]:
        """Create child jobs for processing each chapter."""
        child_job_ids = []

        # Get processing configuration from parent job
        voice_config = parent_job.config.get("voice_config", {}) if parent_job.config else {}
        processing_mode = (
            parent_job.config.get("processing_mode", "single_voice")
            if parent_job.config
            else "single_voice"
        )

        for chapter_file in chapter_files:
            # Create child job
            child_job = Job(
                id=str(uuid4()),
                user_id=parent_job.user_id,
                title=f"{parent_job.title} - {chapter_file['title']}",
                description=f"Chapter {chapter_file['chapter_number']} of {parent_job.title}",
                status=JobStatus.PENDING,
                config={
                    "parent_job_id": parent_job.id,
                    "chapter_number": chapter_file["chapter_number"],
                    "voice_config": voice_config,
                    "processing_mode": processing_mode,
                },
                input_file_key=chapter_file["file_key"],
            )

            self.db_session.add(child_job)
            child_job_ids.append(child_job.id)

            logger.info(
                f"Created child job {child_job.id} for chapter {chapter_file['chapter_number']}"
            )

        # Commit all child jobs
        await self.db_session.commit()

        # Schedule all child jobs for processing
        from storytime.worker.tasks import process_job

        for job_id in child_job_ids:
            try:
                process_job.delay(job_id)
                logger.info(f"Scheduled child job {job_id} for processing")
            except Exception as e:
                logger.warning(f"Could not schedule child job {job_id}: {e}")

        return child_job_ids

    async def aggregate_chapter_results(self, job_id: str) -> dict[str, Any]:
        """Aggregate results from all chapter processing jobs."""
        # Get the parent job
        parent_job = await self.job_processor._get_job(job_id)
        if not parent_job:
            raise ValueError(f"Parent job {job_id} not found")

        # Get child job IDs from result data
        child_job_ids = parent_job.result_data.get("child_job_ids", [])
        if not child_job_ids:
            logger.warning(f"No child jobs found for parent job {job_id}")
            return {}

        # Query all child jobs
        result = await self.db_session.execute(select(Job).where(Job.id.in_(child_job_ids)))
        child_jobs = result.scalars().all()

        # Aggregate results
        completed_chapters = []
        failed_chapters = []
        total_duration = 0.0

        for child_job in sorted(child_jobs, key=lambda j: j.config.get("chapter_number", 0)):
            chapter_info = {
                "chapter_number": child_job.config.get("chapter_number"),
                "title": child_job.title,
                "status": child_job.status,
            }

            if child_job.status == JobStatus.COMPLETED:
                chapter_info["audio_file"] = child_job.output_file_key
                chapter_info["duration"] = child_job.duration
                if child_job.duration:
                    total_duration += child_job.duration
                completed_chapters.append(chapter_info)
            elif child_job.status == JobStatus.FAILED:
                chapter_info["error"] = child_job.error_message
                failed_chapters.append(chapter_info)

        return {
            "total_chapters": len(child_jobs),
            "completed_chapters": len(completed_chapters),
            "failed_chapters": len(failed_chapters),
            "total_duration_seconds": total_duration,
            "chapters": completed_chapters + failed_chapters,
        }
