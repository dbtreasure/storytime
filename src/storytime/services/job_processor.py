"""Unified job processor handling both simple and book jobs."""

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.database import Job, JobStatus, JobStep, StepStatus
from storytime.infrastructure.spaces import SpacesClient
from storytime.models import JobResponse, JobStepResponse
from storytime.services.book_analyzer import BookAnalyzer, ChapterInfo
from storytime.services.content_analyzer import ContentAnalyzer
from storytime.services.preprocessing_service import PreprocessingService
from storytime.services.tts_generator import TTSGenerator
from storytime.services.web_scraping import WebScrapingService

logger = logging.getLogger(__name__)


class JobProcessor:
    """Process both simple text jobs and full book jobs."""

    def __init__(
        self,
        db_session: AsyncSession,
        spaces_client: SpacesClient,
        tts_generator: TTSGenerator | None = None,
        preprocessing_service: PreprocessingService | None = None,
        web_scraping_service: WebScrapingService | None = None,
        content_analyzer: ContentAnalyzer | None = None,
    ):
        self.db_session = db_session
        self.spaces_client = spaces_client
        self.tts_generator = tts_generator or TTSGenerator()
        self.preprocessing_service = preprocessing_service or PreprocessingService()
        self.web_scraping_service = web_scraping_service or WebScrapingService()
        self.content_analyzer = content_analyzer or ContentAnalyzer()
        self.book_analyzer = BookAnalyzer()

    def _is_book_job(self, job: Job) -> bool:
        """Determine if a job should be processed as a book."""
        if job.config:
            return job.config.get("job_type") == "book_processing"
        return False

    def _was_job_type_explicitly_set(self, job: Job) -> bool:
        """Check if job type was explicitly set by user (vs auto-detected)."""
        if job.config:
            # If job_type is set to something other than the default, it was likely explicit
            # We could also store a flag for this, but for now assume TEXT_TO_AUDIO means auto-detected
            job_type = job.config.get("job_type")
            return job_type == "book_processing"  # Book processing is always explicit
        return False

    async def _reanalyze_url_content(self, job: Job) -> Job:
        """Re-analyze URL content after scraping to determine optimal job type."""
        if not self.content_analyzer.is_available():
            logger.info("Content analyzer not available, keeping original job type")
            return job

        try:
            logger.info(f"Re-analyzing URL content for job {job.id}")

            # Scrape the URL content
            url = job.config["url"]
            scraping_result = await self.web_scraping_service.extract_content(url)
            scraped_content = scraping_result["content"]

            # Analyze the scraped content
            detected_type = await self.content_analyzer.analyze_content(
                scraped_content,
                job.title
            )

            # Update job config if type changed
            current_type = job.config.get("job_type", "text_to_audio")
            if detected_type.value != current_type:
                logger.info(f"URL content analysis changed job type: {current_type} -> {detected_type.value}")

                # Update job config in database
                job.config["job_type"] = detected_type.value
                await self._update_job_config(job.id, job.config)

                # Refresh job object
                job = await self._get_job(job.id)
            else:
                logger.info(f"URL content analysis confirmed job type: {detected_type.value}")

        except Exception as e:
            logger.warning(f"URL content re-analysis failed, keeping original job type: {e}")

        return job

    async def process_job(self, job_id: str) -> JobResponse:
        """Process a job based on its type."""
        logger.info(f"Starting job processing for job_id={job_id}")

        # Get job from database
        job = await self._get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Update job status to processing
        await self._update_job_status(job_id, JobStatus.PROCESSING, started_at=datetime.utcnow())

        try:
            # For URL jobs, re-analyze content after scraping if job type wasn't explicitly set
            if job.config and job.config.get("url") and not self._was_job_type_explicitly_set(job):
                job = await self._reanalyze_url_content(job)

            # Route based on job type
            if self._is_book_job(job):
                result = await self._process_book_job(job)
            else:
                result = await self._process_text_to_audio_job(job)

            # Update job status to completed
            await self._update_job_status(
                job_id,
                JobStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.utcnow(),
                result_data=result,
            )

            logger.info(f"Job {job_id} completed successfully")
            return await self._get_job_response(job_id)

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e!s}", exc_info=True)
            await self._update_job_status(
                job_id, JobStatus.FAILED, error_message=str(e), completed_at=datetime.utcnow()
            )
            raise

    async def _process_book_job(self, job: Job) -> dict[str, Any]:
        """Process a full book job with chapter splitting."""
        logger.info(f"Processing book job {job.id}")

        # Step 1: Load book text
        load_step = await self._create_job_step(
            job.id, "load_book", 0, "Load book text from storage"
        )
        await self._update_job_step(load_step.id, StepStatus.RUNNING, started_at=datetime.utcnow())

        try:
            book_text = await self._load_book_text(job)
            await self._update_job_step(
                load_step.id, StepStatus.COMPLETED, progress=1.0, completed_at=datetime.utcnow()
            )
        except Exception as e:  # pragma: no cover - basic error propagation
            await self._update_job_step(
                load_step.id,
                StepStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

        # Step 2: Analyze book structure
        analyze_step = await self._create_job_step(
            job.id, "analyze_structure", 1, "Analyze book structure and detect chapters"
        )
        await self._update_job_step(
            analyze_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
        )

        try:
            chapters = self.book_analyzer.analyze_book(book_text)
            await self._update_job_step(
                analyze_step.id,
                StepStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.utcnow(),
                step_metadata={"chapter_count": len(chapters)},
            )
        except Exception as e:
            await self._update_job_step(
                analyze_step.id,
                StepStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

        # Step 3: Split and save chapters
        split_step = await self._create_job_step(
            job.id, "split_chapters", 2, "Split book into individual chapters"
        )
        await self._update_job_step(split_step.id, StepStatus.RUNNING, started_at=datetime.utcnow())

        try:
            chapter_files = await self._split_and_save_chapters(job.id, book_text, chapters)
            await self._update_job_step(
                split_step.id, StepStatus.COMPLETED, progress=1.0, completed_at=datetime.utcnow()
            )
        except Exception as e:
            await self._update_job_step(
                split_step.id,
                StepStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

        # Step 4: Create child jobs
        create_jobs_step = await self._create_job_step(
            job.id, "create_chapter_jobs", 3, "Create processing jobs for each chapter"
        )
        await self._update_job_step(
            create_jobs_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
        )

        try:
            child_job_ids = await self._create_chapter_jobs(job, chapters, chapter_files)
            await self._update_job_step(
                create_jobs_step.id,
                StepStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.utcnow(),
                step_metadata={"child_job_ids": child_job_ids},
            )
        except Exception as e:
            await self._update_job_step(
                create_jobs_step.id,
                StepStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

        await self._update_job_status(job.id, JobStatus.PROCESSING, progress=1.0)

        return {
            "processing_type": "book_splitting",
            "chapter_count": len(chapters),
            "child_job_ids": child_job_ids,
            "chapter_files": chapter_files,
            "total_word_count": len(book_text.split()),
        }

    async def _process_text_to_audio_job(self, job: Job) -> dict[str, Any]:
        """Process a simple text-to-audio conversion job."""
        logger.info(f"Processing text-to-audio job {job.id}")

        # Step 1: Content Acquisition (includes URL scraping if needed)
        content_step = await self._create_job_step(
            job.id, "acquire_content", 0, "Acquire text content for processing"
        )

        try:
            # Update content step to running
            await self._update_job_step(
                content_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
            )

            # Get text content based on input type
            if job.config and job.config.get("content"):
                text_content = job.config["content"]
                content_source = "direct_input"
            elif job.config and job.config.get("url"):
                # Scrape content from URL
                logger.info(f"Scraping content from URL for job {job.id}")
                url = job.config["url"]
                scraping_result = await self.web_scraping_service.extract_content(url)
                text_content = scraping_result["content"]
                content_source = "url_scraping"

                # Store scraping metadata
                await self._update_job_step(
                    content_step.id,
                    StepStatus.RUNNING,
                    step_metadata={
                        "description": "Scrape content from URL",
                        "url": url,
                        "character_count": scraping_result["character_count"],
                        "estimated_words": scraping_result["estimated_words"],
                        "scraped_title": scraping_result.get("title"),
                    },
                )
            elif job.input_file_key:
                # Download from file storage
                text_content = await self.spaces_client.download_text_file(job.input_file_key)
                content_source = "file_upload"
            else:
                raise ValueError("No text content, file, or URL provided")

            # Complete content acquisition step
            await self._update_job_step(
                content_step.id,
                StepStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.utcnow(),
                step_metadata={
                    "content_source": content_source,
                    "character_count": len(text_content),
                },
            )

            # Update overall job progress (content acquired)
            await self._update_job_status(job.id, JobStatus.PROCESSING, progress=0.33)

            # Step 2: Text Preprocessing
            preprocessing_step = await self._create_job_step(
                job.id, "preprocess_text", 1, "Preprocess text content for TTS"
            )

            # Update preprocessing step to running
            await self._update_job_step(
                preprocessing_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
            )

            # Preprocess text content
            logger.info(f"Calling preprocessing service for job {job.id}")
            processed_text = await self.preprocessing_service.preprocess_text(
                text_content, job.config
            )
            logger.info(f"Preprocessing complete for job {job.id}")

            # Complete preprocessing step
            await self._update_job_step(
                preprocessing_step.id,
                StepStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.utcnow(),
            )

            # Update overall job progress (preprocessing complete)
            await self._update_job_status(job.id, JobStatus.PROCESSING, progress=0.66)

            # Step 3: TTS Generation
            tts_step = await self._create_job_step(
                job.id, "text_to_audio", 2, "Convert processed text to audio using TTS"
            )

            # Update TTS step to running
            await self._update_job_step(
                tts_step.id, StepStatus.RUNNING, started_at=datetime.utcnow()
            )

            # Get voice configuration
            voice_config = job.config.get("voice_config", {}) if job.config else {}

            # Generate audio using simple TTS with processed text
            audio_data = await self.tts_generator.generate_simple_audio(
                text=processed_text, voice_config=voice_config
            )

            # Upload audio to storage
            audio_key = f"jobs/{job.id!s}/audio.mp3"
            await self.spaces_client.upload_audio_file(audio_key, audio_data)

            # Calculate audio metadata
            audio_metadata = {
                "file_size_bytes": len(audio_data),
                "format": "audio/mpeg",
                # Duration would need to be calculated from audio data
                # For now, we'll leave it as None
                "duration_seconds": None,
            }

            # Update job with output file reference and metadata
            await self._update_job_output(job.id, audio_key, audio_metadata)

            # Complete TTS step
            await self._update_job_step(
                tts_step.id, StepStatus.COMPLETED, progress=1.0, completed_at=datetime.utcnow()
            )

            # Update overall job progress (complete)
            await self._update_job_status(job.id, JobStatus.PROCESSING, progress=1.0)

            return {
                "processing_type": "single_voice",
                "audio_key": audio_key,
                "text_length": len(text_content),
                "voice_config": voice_config,
                "content_source": content_source,
            }

        except Exception as e:
            logger.error(f"Text-to-audio job processing failed: {e}", exc_info=True)

            # Mark the current step as failed
            # We need to determine which step was running when the error occurred
            try:
                # Check steps in reverse order to find the most recent one
                for step_name in ["text_to_audio", "preprocess_text", "acquire_content"]:
                    step_result = await self.db_session.execute(
                        select(JobStep).where(
                            JobStep.job_id == job.id, JobStep.step_name == step_name
                        )
                    )
                    step = step_result.scalar_one_or_none()

                    if step and step.status == StepStatus.RUNNING:
                        # Found the running step that failed
                        await self._update_job_step(
                            step.id,
                            StepStatus.FAILED,
                            error_message=str(e),
                            completed_at=datetime.utcnow(),
                        )
                        break
            except Exception as db_error:
                logger.error(f"Failed to update step status: {db_error}")

            raise

    # Database helper methods
    async def _get_job(self, job_id: str) -> Job | None:
        """Get job by ID."""
        result = await self.db_session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: float | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        result_data: dict[str, Any] | None = None,
    ) -> None:
        """Update job status and metadata."""
        update_data = {"status": status, "updated_at": datetime.utcnow()}

        if progress is not None:
            update_data["progress"] = progress
        if error_message is not None:
            update_data["error_message"] = error_message
        if started_at is not None:
            update_data["started_at"] = started_at
        if completed_at is not None:
            update_data["completed_at"] = completed_at
        if result_data is not None:
            update_data["result_data"] = result_data

        await self.db_session.execute(update(Job).where(Job.id == job_id).values(**update_data))
        await self.db_session.commit()

    async def _update_job_output(
        self, job_id: str, output_file_key: str, metadata: dict | None = None
    ) -> None:
        """Update job with output file reference and optional metadata."""
        update_values = {"output_file_key": output_file_key, "updated_at": datetime.utcnow()}

        # Add metadata to result_data if provided
        if metadata:
            # Get current job to preserve existing result_data
            result = await self.db_session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one()

            # Merge metadata into result_data
            result_data = job.result_data or {}
            result_data.update(metadata)
            update_values["result_data"] = result_data

        await self.db_session.execute(update(Job).where(Job.id == job_id).values(**update_values))
        await self.db_session.commit()

    async def _update_job_config(self, job_id: str, config: dict[str, Any]) -> None:
        """Update job configuration."""
        await self.db_session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(config=config, updated_at=datetime.utcnow())
        )
        await self.db_session.commit()

    async def _create_job_step(
        self, job_id: str, step_name: str, step_order: int, description: str = ""
    ) -> JobStep:
        """Create a new job step."""
        step = JobStep(
            job_id=job_id,
            step_name=step_name,
            step_order=step_order,
            status=StepStatus.PENDING,
            progress=0.0,
            step_metadata={"description": description} if description else {},
        )

        self.db_session.add(step)
        await self.db_session.commit()
        await self.db_session.refresh(step)
        return step

    async def _update_job_step(
        self,
        step_id: str,
        status: StepStatus,
        progress: float | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        step_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update job step status and metadata."""
        update_data = {"status": status, "updated_at": datetime.utcnow()}

        if progress is not None:
            update_data["progress"] = progress
        if error_message is not None:
            update_data["error_message"] = error_message
        if started_at is not None:
            update_data["started_at"] = started_at
        if completed_at is not None:
            update_data["completed_at"] = completed_at
        if step_metadata is not None:
            update_data["step_metadata"] = step_metadata

        await self.db_session.execute(
            update(JobStep).where(JobStep.id == step_id).values(**update_data)
        )
        await self.db_session.commit()

    async def _get_job_response(self, job_id: str) -> JobResponse:
        """Get job with steps as response model."""
        # Get job
        result = await self.db_session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Get job steps
        steps_result = await self.db_session.execute(
            select(JobStep).where(JobStep.job_id == job_id).order_by(JobStep.step_order)
        )
        steps = steps_result.scalars().all()

        step_responses = [
            JobStepResponse(
                id=step.id,
                step_name=step.step_name,
                step_order=step.step_order,
                status=step.status,
                progress=step.progress,
                error_message=step.error_message,
                step_metadata=step.step_metadata,
                created_at=step.created_at,
                updated_at=step.updated_at,
                started_at=step.started_at,
                completed_at=step.completed_at,
                duration=step.duration,
            )
            for step in steps
        ]

        return JobResponse(
            id=job.id,
            user_id=job.user_id,
            parent_job_id=job.parent_id,
            title=job.title,
            description=job.description,
            status=job.status,
            progress=job.progress,
            error_message=job.error_message,
            config=job.config,
            result_data=job.result_data,
            input_file_key=job.input_file_key,
            output_file_key=job.output_file_key,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration=job.duration,
            steps=step_responses,
        )

    async def _load_book_text(self, job: Job) -> str:
        """Load and preprocess book text from various sources."""
        if job.config and job.config.get("content"):
            raw_text = job.config["content"]
        elif job.config and job.config.get("url"):
            url = job.config["url"]
            logger.info(f"Scraping content from URL for job {job.id}")
            scraping_result = await self.web_scraping_service.extract_content(url)
            raw_text = scraping_result["content"]
        elif job.input_file_key:
            raw_text = await self.spaces_client.download_text_file(job.input_file_key)
        else:
            raise ValueError("No book content, file, or URL provided")

        logger.info(f"Preprocessing book text for job {job.id}")
        processed_text = await self.preprocessing_service.preprocess_text(raw_text, job.config)
        return processed_text

    async def _split_and_save_chapters(
        self, job_id: str, book_text: str, chapters: list[ChapterInfo]
    ) -> list[dict[str, Any]]:
        chapter_files = []
        for i, chapter in enumerate(chapters):
            chapter_text = book_text[chapter.start_position : chapter.end_position]
            chapter_number = chapter.chapter_number or (i + 1)
            file_key = f"jobs/{job_id}/chapters/chapter_{chapter_number:03d}.txt"
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
        return chapter_files

    async def _create_chapter_jobs(
        self, parent_job: Job, chapters: list[ChapterInfo], chapter_files: list[dict[str, Any]]
    ) -> list[str]:
        child_job_ids = []
        voice_config = parent_job.config.get("voice_config", {}) if parent_job.config else {}

        for chapter_file in chapter_files:
            child_job = Job(
                id=str(uuid4()),
                user_id=parent_job.user_id,
                parent_id=parent_job.id,
                title=f"{parent_job.title} - {chapter_file['title']}",
                description=f"Chapter {chapter_file['chapter_number']} of {parent_job.title}",
                status=JobStatus.PENDING,
                config={
                    "parent_job_id": parent_job.id,
                    "chapter_number": chapter_file["chapter_number"],
                    "voice_config": voice_config,
                    "job_type": "text_to_audio",  # Child jobs are always simple text-to-audio
                },
                input_file_key=chapter_file["file_key"],
            )
            self.db_session.add(child_job)
            child_job_ids.append(child_job.id)

        await self.db_session.commit()

        from storytime.worker.tasks import process_job

        for child_id in child_job_ids:
            try:
                process_job.delay(child_id)
            except Exception as e:  # pragma: no cover - scheduling may fail in tests
                logger.warning(f"Could not schedule child job {child_id}: {e}")

        return child_job_ids

    async def aggregate_chapter_results(self, job_id: str) -> dict[str, Any]:
        parent_job = await self._get_job(job_id)
        if not parent_job:
            raise ValueError(f"Parent job {job_id} not found")

        child_job_ids = (
            parent_job.result_data.get("child_job_ids", []) if parent_job.result_data else []
        )
        if not child_job_ids:
            logger.warning(f"No child jobs found for parent job {job_id}")
            return {}

        result = await self.db_session.execute(select(Job).where(Job.id.in_(child_job_ids)))
        child_jobs = result.scalars().all()

        completed = []
        failed = []
        total_duration = 0.0
        for child in sorted(child_jobs, key=lambda j: j.config.get("chapter_number", 0)):
            info = {
                "chapter_number": child.config.get("chapter_number"),
                "title": child.title,
                "status": child.status,
            }
            if child.status == JobStatus.COMPLETED:
                info["audio_file"] = child.output_file_key
                info["duration"] = child.duration
                if child.duration:
                    total_duration += child.duration
                completed.append(info)
            elif child.status == JobStatus.FAILED:
                info["error"] = child.error_message
                failed.append(info)

        return {
            "total_chapters": len(child_jobs),
            "completed_chapters": len(completed),
            "failed_chapters": len(failed),
            "total_duration_seconds": total_duration,
            "chapters": completed + failed,
        }
