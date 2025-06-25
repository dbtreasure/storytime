"""OpenAI Responses API service with vector store integration for content search and Q&A."""

import logging
from typing import Any

from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.services.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)


class ResponsesAPIVectorStoreService:
    """Service for OpenAI Responses API with vector store file search."""

    def __init__(self, openai_client: OpenAI, db_session: AsyncSession):
        self.openai_client = openai_client
        self.db_session = db_session
        self.vector_store_manager = VectorStoreManager(openai_client, db_session)

    async def search_job_content(
        self, user_id: str, job_id: str, query: str, max_results: int = 5
    ) -> dict[str, Any]:
        """Search within specific job content using vector store."""
        try:
            # Get user's vector store ID
            vector_store_id = await self.vector_store_manager.get_user_vector_store_id(user_id)
            if not vector_store_id:
                return {"success": False, "error": "No vector store found for user", "results": []}

            # Create response with file search tool
            response = self.openai_client.responses.create(
                model="gpt-4o-mini",
                input=f"Search for the following in the audiobook content (job_id: {job_id}): {query}",
                tools=[
                    {
                        "type": "file_search",
                        "vector_store_ids": [vector_store_id],
                        "max_num_results": max_results,
                    }
                ],
                include=["file_search_call.results"],  # Include search results in response
            )

            # Extract search results from response
            results = []
            response_text = ""

            if hasattr(response, "output"):
                for output_item in response.output:
                    if output_item.type == "file_search_call":
                        # Extract search results
                        if hasattr(output_item, "search_results") and output_item.search_results:
                            results.extend(output_item.search_results)
                    elif output_item.type == "message" and hasattr(output_item, "content"):
                        # Extract the response text
                        for content_item in output_item.content:
                            if content_item.type == "output_text":
                                response_text = content_item.text

            return {
                "success": True,
                "query": query,
                "job_id": job_id,
                "results": results,
                "response_text": response_text,
            }

        except Exception as e:
            logger.error(f"Error searching job content: {e}")
            return {"success": False, "error": str(e), "results": []}

    async def ask_question_about_job(
        self, user_id: str, job_id: str, question: str
    ) -> dict[str, Any]:
        """Ask a question about specific job content."""
        try:
            # Get user's vector store ID
            vector_store_id = await self.vector_store_manager.get_user_vector_store_id(user_id)
            if not vector_store_id:
                return {"success": False, "error": "No vector store found for user", "answer": ""}

            # Get job information for context
            from sqlalchemy import select

            from storytime.database import Job

            result = await self.db_session.execute(
                select(Job).where(Job.id == job_id, Job.user_id == user_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                return {"success": False, "error": "Job not found or access denied", "answer": ""}

            # Create response with file search to answer question
            response = self.openai_client.responses.create(
                model="gpt-4o-mini",
                input=f"""Answer the following question about the audiobook "{job.title}" (job_id: {job_id}):

Question: {question}

Use the file search to find relevant information from the audiobook content to answer the question accurately.""",
                tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
            )

            # Extract answer from response
            answer = ""
            if hasattr(response, "output"):
                for output_item in response.output:
                    if output_item.type == "message" and hasattr(output_item, "content"):
                        for content_item in output_item.content:
                            if content_item.type == "output_text":
                                answer = content_item.text

            return {
                "success": True,
                "question": question,
                "job_id": job_id,
                "job_title": job.title,
                "answer": answer,
                "model": "gpt-4o-mini",
            }

        except Exception as e:
            logger.error(f"Error answering question about job: {e}")
            return {"success": False, "error": str(e), "answer": ""}

    async def search_library(
        self, user_id: str, query: str, max_results: int = 10
    ) -> dict[str, Any]:
        """Search across user's entire audiobook library."""
        try:
            # Get user's vector store ID
            vector_store_id = await self.vector_store_manager.get_user_vector_store_id(user_id)
            if not vector_store_id:
                return {"success": False, "error": "No vector store found for user", "results": []}

            # Create response with file search across all user's content
            response = self.openai_client.responses.create(
                model="gpt-4o-mini",
                input=f"""Search across the entire audiobook library for: {query}

Find relevant results across all books and provide excerpts with book titles.
Group results by book when possible and indicate which audiobook each result comes from.""",
                tools=[
                    {
                        "type": "file_search",
                        "vector_store_ids": [vector_store_id],
                        "max_num_results": max_results,
                    }
                ],
                include=["file_search_call.results"],
            )

            # Extract search results
            results = []
            response_text = ""

            if hasattr(response, "output"):
                for output_item in response.output:
                    if output_item.type == "file_search_call":
                        if hasattr(output_item, "search_results") and output_item.search_results:
                            results.extend(output_item.search_results)
                    elif output_item.type == "message" and hasattr(output_item, "content"):
                        for content_item in output_item.content:
                            if content_item.type == "output_text":
                                response_text = content_item.text

            return {
                "success": True,
                "query": query,
                "results": results,
                "response_text": response_text,
            }

        except Exception as e:
            logger.error(f"Error searching library: {e}")
            return {"success": False, "error": str(e), "results": []}
