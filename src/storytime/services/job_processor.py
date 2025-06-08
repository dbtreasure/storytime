"""Job processing router that intelligently routes between different workflow types."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.database import Job, JobStatus, JobStep, JobType, StepStatus
from storytime.infrastructure.spaces import SpacesClient
from storytime.models import JobResponse, JobStepResponse
from storytime.services.content_analyzer import ContentAnalyzer
from storytime.services.tts_generator import TTSGenerator
from storytime.workflows.audio_generation import AudioGenerationWorkflow
from storytime.workflows.chapter_parsing import ChapterParsingWorkflow

logger = logging.getLogger(__name__)


class JobProcessor:
    """Main orchestration service for processing jobs of different types."""

    def __init__(
        self,
        db_session: AsyncSession,
        spaces_client: SpacesClient,
        content_analyzer: ContentAnalyzer | None = None,
        tts_generator: TTSGenerator | None = None,
    ):
        self.db_session = db_session
        self.spaces_client = spaces_client
        self.content_analyzer = content_analyzer or ContentAnalyzer()
        self.tts_generator = tts_generator or TTSGenerator()

    async def process_job(self, job_id: str) -> JobResponse:
        """Main entry point for processing a job based on its type."""
        logger.info(f"Starting job processing for job_id={job_id}")

        # Get job from database
        job = await self._get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Update job status to processing
        await self._update_job_status(job_id, JobStatus.PROCESSING, started_at=datetime.utcnow())

        try:
            # Route to appropriate processor based on job type
            if job.job_type == JobType.SINGLE_VOICE:
                result = await self._process_single_voice_job(job)
            elif job.job_type == JobType.MULTI_VOICE:
                result = await self._process_multi_voice_job(job)
            elif job.job_type == JobType.BOOK_PROCESSING:
                result = await self._process_book_job(job)
            elif job.job_type == JobType.CHAPTER_PARSING:
                result = await self._process_chapter_parsing_job(job)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")

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

    async def _process_single_voice_job(self, job: Job) -> dict[str, Any]:
        """Process a simple single-voice TTS job."""
        logger.info(f"Processing single voice job {job.id}")

        # Create processing steps
        steps = [
            ("load_content", "Loading text content"),
            ("generate_audio", "Generating audio with TTS"),
            ("upload_audio", "Uploading audio to storage"),
        ]
        await self._create_job_steps(job.id, steps)

        # Step 1: Load content
        await self._update_step_status(job.id, "load_content", StepStatus.RUNNING)

        if job.input_file_key:
            content = await self.spaces_client.download_text_file(job.input_file_key)
        elif job.config and "content" in job.config:
            content = job.config["content"]
        else:
            raise ValueError("No content source specified")

        await self._update_step_status(job.id, "load_content", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 0.33)

        # Step 2: Generate audio
        await self._update_step_status(job.id, "generate_audio", StepStatus.RUNNING)

        voice_config = job.config.get("voice_config", {}) if job.config else {}
        audio_data = await self.tts_generator.generate_simple_audio(
            text=content, voice_config=voice_config
        )

        await self._update_step_status(job.id, "generate_audio", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 0.66)

        # Step 3: Upload audio
        await self._update_step_status(job.id, "upload_audio", StepStatus.RUNNING)

        audio_key = f"jobs/{job.id}/audio.mp3"
        await self.spaces_client.upload_audio_file(audio_key, audio_data)

        # Update job with output file reference
        await self._update_job_output_file(job.id, audio_key)

        await self._update_step_status(job.id, "upload_audio", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 1.0)

        return {
            "audio_key": audio_key,
            "content_length": len(content),
            "processing_type": "single_voice",
        }

    async def _process_multi_voice_job(self, job: Job) -> dict[str, Any]:
        """Process a complex multi-voice job using Junjo workflows."""
        logger.info(f"Processing multi-voice job {job.id}")

        # Create processing steps
        steps = [
            ("parse_chapter", "Parsing text into segments"),
            ("assign_voices", "Assigning voices to characters"),
            ("generate_audio", "Generating multi-voice audio"),
            ("upload_results", "Uploading results to storage"),
        ]
        await self._create_job_steps(job.id, steps)

        # Step 1: Parse chapter using Junjo workflow
        await self._update_step_status(job.id, "parse_chapter", StepStatus.RUNNING)

        if job.input_file_key:
            content = await self.spaces_client.download_text_file(job.input_file_key)
        elif job.config and "content" in job.config:
            content = job.config["content"]
        else:
            raise ValueError("No content source specified")

        # Run chapter parsing workflow
        parsing_workflow = ChapterParsingWorkflow()
        parsing_result = await parsing_workflow.run(
            text_content=content,
            job_id=job.id,
            progress_callback=lambda p: self._update_step_progress(job.id, "parse_chapter", p),
        )

        await self._update_step_status(job.id, "parse_chapter", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 0.25)

        # Step 2: Voice assignment (simplified for now)
        await self._update_step_status(job.id, "assign_voices", StepStatus.RUNNING)

        voice_config = job.config.get("voice_config", {}) if job.config else {}
        # Voice assignment logic would go here

        await self._update_step_status(job.id, "assign_voices", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 0.5)

        # Step 3: Generate audio using audio generation workflow
        await self._update_step_status(job.id, "generate_audio", StepStatus.RUNNING)

        audio_workflow = AudioGenerationWorkflow()
        audio_result = await audio_workflow.run(
            chapter_data=parsing_result,
            voice_config=voice_config,
            job_id=job.id,
            progress_callback=lambda p: self._update_step_progress(job.id, "generate_audio", p),
        )

        await self._update_step_status(job.id, "generate_audio", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 0.75)

        # Step 4: Upload results
        await self._update_step_status(job.id, "upload_results", StepStatus.RUNNING)

        # Upload chapter data and audio files
        chapter_data_key = f"jobs/{job.id}/chapter_data.json"
        await self.spaces_client.upload_json_file(chapter_data_key, parsing_result)

        audio_key = f"jobs/{job.id}/audio.mp3"
        await self.spaces_client.upload_audio_file(audio_key, audio_result["audio_data"])

        # Update job with output file reference
        await self._update_job_output_file(job.id, audio_key)

        await self._update_step_status(job.id, "upload_results", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 1.0)

        return {
            "audio_key": audio_key,
            "chapter_data_key": chapter_data_key,
            "segment_count": len(parsing_result.get("segments", [])),
            "character_count": len(parsing_result.get("characters", {})),
            "processing_type": "multi_voice",
        }

    async def _process_book_job(self, job: Job) -> dict[str, Any]:
        """Process a full book by splitting into chapters and creating child jobs."""
        logger.info(f"Processing book job {job.id}")

        # Create processing steps
        steps = [
            ("load_book", "Loading book content"),
            ("split_chapters", "Splitting book into chapters"),
            ("create_chapter_jobs", "Creating chapter processing jobs"),
            ("monitor_progress", "Monitoring chapter job progress"),
        ]
        await self._create_job_steps(job.id, steps)

        # Step 1: Load book content
        await self._update_step_status(job.id, "load_book", StepStatus.RUNNING)

        if job.input_file_key:
            content = await self.spaces_client.download_text_file(job.input_file_key)
        else:
            raise ValueError("Book processing requires input file")

        await self._update_step_status(job.id, "load_book", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 0.1)

        # Step 2: Split into chapters
        await self._update_step_status(job.id, "split_chapters", StepStatus.RUNNING)

        chapters = await self.content_analyzer.split_book_into_chapters(content)

        await self._update_step_status(job.id, "split_chapters", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 0.2)

        # Step 3: Create chapter jobs
        await self._update_step_status(job.id, "create_chapter_jobs", StepStatus.RUNNING)

        chapter_job_ids = []
        for i, chapter_content in enumerate(chapters):
            chapter_job = await self._create_chapter_job(
                parent_job_id=job.id,
                chapter_number=i + 1,
                content=chapter_content,
                user_id=job.user_id,
                voice_config=job.config.get("voice_config", {}) if job.config else {},
            )
            chapter_job_ids.append(chapter_job.id)

        await self._update_step_status(
            job.id, "create_chapter_jobs", StepStatus.COMPLETED, progress=1.0
        )
        await self._update_job_progress(job.id, 0.3)

        # Step 4: Monitor chapter job progress (simplified)
        await self._update_step_status(job.id, "monitor_progress", StepStatus.RUNNING)

        # In a real implementation, this would monitor child jobs and update progress
        # For now, we'll mark it as completed

        await self._update_step_status(
            job.id, "monitor_progress", StepStatus.COMPLETED, progress=1.0
        )
        await self._update_job_progress(job.id, 1.0)

        return {
            "chapter_count": len(chapters),
            "chapter_job_ids": chapter_job_ids,
            "processing_type": "book_processing",
        }

    async def _process_chapter_parsing_job(self, job: Job) -> dict[str, Any]:
        """Process a chapter parsing only job."""
        logger.info(f"Processing chapter parsing job {job.id}")

        # Create processing steps
        steps = [
            ("load_content", "Loading chapter content"),
            ("parse_segments", "Parsing text into segments"),
            ("analyze_characters", "Analyzing characters"),
            ("save_results", "Saving parsing results"),
        ]
        await self._create_job_steps(job.id, steps)

        # Step 1: Load content
        await self._update_step_status(job.id, "load_content", StepStatus.RUNNING)

        if job.input_file_key:
            content = await self.spaces_client.download_text_file(job.input_file_key)
        elif job.config and "content" in job.config:
            content = job.config["content"]
        else:
            raise ValueError("No content source specified")

        await self._update_step_status(job.id, "load_content", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 0.25)

        # Step 2-4: Run chapter parsing workflow
        await self._update_step_status(job.id, "parse_segments", StepStatus.RUNNING)

        parsing_workflow = ChapterParsingWorkflow()
        result = await parsing_workflow.run(
            text_content=content,
            job_id=job.id,
            progress_callback=lambda p: self._update_job_progress(job.id, 0.25 + (p * 0.75)),
        )

        await self._update_step_status(job.id, "parse_segments", StepStatus.COMPLETED, progress=1.0)
        await self._update_step_status(
            job.id, "analyze_characters", StepStatus.COMPLETED, progress=1.0
        )
        await self._update_step_status(job.id, "save_results", StepStatus.COMPLETED, progress=1.0)
        await self._update_job_progress(job.id, 1.0)

        return result

    # Helper methods for database operations

    async def _get_job(self, job_id: str) -> Job | None:
        """Get job from database."""
        result = await self.db_session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def _get_job_response(self, job_id: str) -> JobResponse:
        """Get job with steps as response model."""
        job = await self._get_job(job_id)
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
            book_id=job.book_id,
            title=job.title,
            description=job.description,
            job_type=job.job_type,
            source_type=job.source_type,
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

    async def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: float | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        result_data: dict[str, Any] | None = None,
    ):
        """Update job status and related fields."""
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

    async def _update_job_progress(self, job_id: str, progress: float):
        """Update job progress."""
        await self.db_session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(progress=progress, updated_at=datetime.utcnow())
        )
        await self.db_session.commit()

    async def _update_job_output_file(self, job_id: str, output_file_key: str):
        """Update job output file reference."""
        await self.db_session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(output_file_key=output_file_key, updated_at=datetime.utcnow())
        )
        await self.db_session.commit()

    async def _create_job_steps(self, job_id: str, steps: list[tuple[str, str]]):
        """Create job steps for tracking progress."""
        step_objects = []
        for i, (step_name, description) in enumerate(steps):
            step = JobStep(
                job_id=job_id,
                step_name=step_name,
                step_order=i,
                status=StepStatus.PENDING,
                progress=0.0,
                step_metadata={"description": description},
            )
            step_objects.append(step)

        self.db_session.add_all(step_objects)
        await self.db_session.commit()

    async def _update_step_status(
        self,
        job_id: str,
        step_name: str,
        status: StepStatus,
        progress: float | None = None,
        error_message: str | None = None,
    ):
        """Update individual step status."""
        update_data = {"status": status, "updated_at": datetime.utcnow()}

        if progress is not None:
            update_data["progress"] = progress
        if error_message is not None:
            update_data["error_message"] = error_message
        if status == StepStatus.RUNNING:
            update_data["started_at"] = datetime.utcnow()
        elif status == StepStatus.COMPLETED:
            update_data["completed_at"] = datetime.utcnow()

        await self.db_session.execute(
            update(JobStep)
            .where(JobStep.job_id == job_id, JobStep.step_name == step_name)
            .values(**update_data)
        )
        await self.db_session.commit()

    async def _update_step_progress(self, job_id: str, step_name: str, progress: float):
        """Update individual step progress."""
        await self.db_session.execute(
            update(JobStep)
            .where(JobStep.job_id == job_id, JobStep.step_name == step_name)
            .values(progress=progress, updated_at=datetime.utcnow())
        )
        await self.db_session.commit()

    async def _create_chapter_job(
        self,
        parent_job_id: str,
        chapter_number: int,
        content: str,
        user_id: str,
        voice_config: dict[str, Any],
    ) -> Job:
        """Create a child job for processing a single chapter."""
        chapter_job = Job(
            user_id=user_id,
            job_type=JobType.MULTI_VOICE,
            source_type="CHAPTER",
            title=f"Chapter {chapter_number}",
            description=f"Processing chapter {chapter_number} from book job {parent_job_id}",
            status=JobStatus.PENDING,
            progress=0.0,
            config={
                "content": content,
                "voice_config": voice_config,
                "parent_job_id": parent_job_id,
                "chapter_number": chapter_number,
            },
        )

        self.db_session.add(chapter_job)
        await self.db_session.commit()
        await self.db_session.refresh(chapter_job)

        return chapter_job
