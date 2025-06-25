"""Vector store management service for OpenAI vector stores."""

import logging
from datetime import datetime

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.database import Job, User, UserVectorStore, VectorStoreFile

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages OpenAI vector stores for users."""

    def __init__(self, openai_client: OpenAI, db_session: AsyncSession):
        self.openai_client = openai_client
        self.db_session = db_session

    async def get_or_create_user_vector_store(self, user_id: str) -> UserVectorStore:
        """Get existing or create new vector store for user."""
        # Check if user already has a vector store
        result = await self.db_session.execute(
            select(UserVectorStore).where(UserVectorStore.user_id == user_id)
        )
        user_vector_store = result.scalar_one_or_none()

        if user_vector_store:
            logger.info(
                f"Found existing vector store for user {user_id}: {user_vector_store.openai_vector_store_id}"
            )
            return user_vector_store

        # Create new vector store in OpenAI
        logger.info(f"Creating new vector store for user {user_id}")

        # Get user info for naming
        user_result = await self.db_session.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one()

        # Create vector store in OpenAI
        vector_store = self.openai_client.vector_stores.create(
            name=f"Storytime Library - {user.email}",
            metadata={"user_id": user_id, "created_by": "storytime"},
        )

        # Save to database
        user_vector_store = UserVectorStore(
            user_id=user_id,
            openai_vector_store_id=vector_store.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db_session.add(user_vector_store)
        await self.db_session.commit()
        await self.db_session.refresh(user_vector_store)

        logger.info(f"Created vector store for user {user_id}: {vector_store.id}")
        return user_vector_store

    async def upload_job_content(self, user_id: str, job: Job, content: str) -> VectorStoreFile:
        """Upload job content to user's vector store."""
        # Get or create user's vector store
        user_vector_store = await self.get_or_create_user_vector_store(user_id)

        # Check if job content is already uploaded
        result = await self.db_session.execute(
            select(VectorStoreFile).where(VectorStoreFile.job_id == job.id)
        )
        existing_file = result.scalar_one_or_none()

        if existing_file:
            logger.info(f"Job {job.id} content already uploaded to vector store")
            return existing_file

        # Create file in OpenAI
        logger.info(f"Uploading content for job {job.id} to vector store")

        # Create a temporary file-like object for upload
        from io import BytesIO

        content_bytes = content.encode("utf-8")
        content_file = BytesIO(content_bytes)
        content_file.name = f"{job.title}.txt"

        # Upload file to OpenAI
        file = self.openai_client.files.create(file=content_file, purpose="assistants")

        # Add file to vector store
        self.openai_client.vector_stores.files.create(
            vector_store_id=user_vector_store.openai_vector_store_id, file_id=file.id
        )

        # Create file metadata
        file_metadata = {
            "job_id": job.id,
            "title": job.title,
            "description": job.description,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "file_size": len(content),
            "openai_file_id": file.id,
        }

        # Save to database
        vector_store_file = VectorStoreFile(
            user_vector_store_id=user_vector_store.id,
            job_id=job.id,
            openai_file_id=file.id,
            file_metadata=file_metadata,
            created_at=datetime.utcnow(),
        )

        self.db_session.add(vector_store_file)

        # Update job with vector store file ID
        job.vector_store_file_id = file.id

        await self.db_session.commit()
        await self.db_session.refresh(vector_store_file)

        logger.info(f"Uploaded job {job.id} content to vector store as file {file.id}")
        return vector_store_file

    async def get_user_vector_store_id(self, user_id: str) -> str | None:
        """Get user's OpenAI vector store ID."""
        result = await self.db_session.execute(
            select(UserVectorStore.openai_vector_store_id).where(UserVectorStore.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_job_files_in_vector_store(self, user_id: str) -> list[VectorStoreFile]:
        """Get all files for a user's vector store."""
        result = await self.db_session.execute(
            select(VectorStoreFile).join(UserVectorStore).where(UserVectorStore.user_id == user_id)
        )
        return result.scalars().all()

    async def delete_job_from_vector_store(self, job_id: str) -> bool:
        """Remove job content from vector store."""
        # Get the vector store file
        result = await self.db_session.execute(
            select(VectorStoreFile).where(VectorStoreFile.job_id == job_id)
        )
        vector_store_file = result.scalar_one_or_none()

        if not vector_store_file:
            logger.warning(f"No vector store file found for job {job_id}")
            return False

        try:
            # Delete file from OpenAI
            self.openai_client.files.delete(vector_store_file.openai_file_id)

            # Delete from database
            await self.db_session.delete(vector_store_file)
            await self.db_session.commit()

            logger.info(f"Deleted job {job_id} from vector store")
            return True

        except Exception as e:
            logger.error(f"Failed to delete job {job_id} from vector store: {e}")
            await self.db_session.rollback()
            return False

    async def cleanup_old_files(self, user_id: str, days_old: int = 30) -> int:
        """Clean up old files from vector store."""
        # This could be implemented to remove files older than X days
        # For now, we'll keep all files as they're valuable for search
        logger.info(
            f"Cleanup requested for user {user_id}, but keeping all files for search capability"
        )
        return 0
