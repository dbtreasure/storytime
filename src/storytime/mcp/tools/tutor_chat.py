"""Tutoring conversation MCP tool for Socratic dialogue."""

import logging
from datetime import datetime
from typing import Any

from openai import OpenAI
from sqlalchemy import select

from storytime.api.settings import get_settings
from storytime.database import Job, TutorConversation
from storytime.mcp.auth import MCPAuthContext
from storytime.mcp.tools.opening_lecture import opening_lecture
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)


async def tutor_chat(
    job_id: str, user_message: str, conversation_history: str = "", context: MCPAuthContext = None
) -> dict[str, Any]:
    """Engage in Socratic tutoring dialogue about audiobook content.

    Args:
        job_id: The audiobook job ID to discuss
        user_message: The user's current message/question
        conversation_history: Previous conversation context (optional)
        context: Authentication context with user and database session

    Returns:
        Dict containing tutor response with success status and dialogue
    """
    try:
        if not context:
            return {"success": False, "error": "Authentication context required", "response": ""}

        # Get job and verify ownership
        result = await context.db_session.execute(
            select(Job).where(Job.id == job_id, Job.user_id == context.user.id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return {"success": False, "error": "Job not found or access denied", "response": ""}

        # Check for existing tutor conversation and intro completion
        conversation_result = await context.db_session.execute(
            select(TutorConversation)
            .where(
                TutorConversation.user_id == context.user.id,
                TutorConversation.job_id == job_id,
                TutorConversation.session_type == "socratic",
            )
            .order_by(TutorConversation.created_at.desc())
        )
        existing_conversation = conversation_result.scalar_one_or_none()

        # If no conversation exists or intro not completed, deliver opening lecture first
        if not existing_conversation or not existing_conversation.is_intro_completed:
            logger.info(
                f"Delivering opening lecture for first-time tutoring session: job={job_id}, user={context.user.id}"
            )

            # Fetch opening lecture content
            lecture_result = await opening_lecture(context.db_session, context.user.id, job_id)

            if lecture_result.get("success"):
                lecture_data = lecture_result["opening_lecture"]

                # Create or update conversation record
                if not existing_conversation:
                    new_conversation = TutorConversation(
                        user_id=context.user.id,
                        job_id=job_id,
                        session_type="socratic",
                        is_intro_completed=True,
                        messages={"opening_lecture": lecture_data, "conversation_history": []},
                        session_metadata={"intro_delivered_at": datetime.utcnow().isoformat()},
                    )
                    context.db_session.add(new_conversation)
                else:
                    existing_conversation.is_intro_completed = True
                    if not existing_conversation.messages:
                        existing_conversation.messages = {}
                    existing_conversation.messages["opening_lecture"] = lecture_data
                    existing_conversation.session_metadata = (
                        existing_conversation.session_metadata or {}
                    )
                    existing_conversation.session_metadata["intro_delivered_at"] = (
                        datetime.utcnow().isoformat()
                    )

                await context.db_session.commit()

                # Auto-generate summary after intro lecture delivery
                try:
                    await generate_conversation_summary(context, job_id, force_update=True)
                    logger.info(
                        f"Auto-generated summary after opening lecture delivery for job {job_id}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to auto-generate summary after intro: {e}")

                # Format and deliver the opening lecture
                intro_text = lecture_data["introduction"]
                concepts_text = lecture_data["key_concepts_overview"]
                objectives_text = lecture_data["learning_objectives"]

                opening_response = f"""Welcome to our tutoring session for '{job.title}'! Let me start with an introduction to prepare you for our Socratic dialogue.

{intro_text}

{concepts_text}

{objectives_text}

You can interrupt me at any time to ask questions or dive deeper into the content. Are you ready to begin our discussion, or do you have any initial questions about what we'll be exploring?"""

                return {
                    "success": True,
                    "response": opening_response,
                    "intro_delivered": True,
                    "lecture_metadata": {
                        "duration_minutes": lecture_data["lecture_duration_minutes"],
                        "engagement_questions": lecture_data["engagement_questions"],
                        "extension_topics": lecture_data["extension_topics"],
                    },
                }
            else:
                # If opening lecture fails, continue with regular tutoring but log the issue
                logger.warning(
                    f"Opening lecture not available for job {job_id}, proceeding with regular tutoring"
                )

        # Get tutoring analysis from job config (grug-brain storage)
        tutoring_data = job.config.get("tutoring_analysis") if job.config else None

        if not tutoring_data:
            return {
                "success": False,
                "error": "Tutoring analysis not available for this content",
                "response": "I don't have tutoring analysis for this content yet. Please try again later.",
            }

        # Create OpenAI client and vector store service for content access
        settings = get_settings()
        if not settings.openai_api_key:
            return {"success": False, "error": "OpenAI API key not configured", "response": ""}

        openai_client = OpenAI(api_key=settings.openai_api_key)
        vector_service = ResponsesAPIVectorStoreService(openai_client, context.db_session)

        # Build tutoring question with embedded instructions (grug-brain approach)
        conversation_context = ""
        if conversation_history:
            conversation_context = f"\n\nPrevious conversation context:\n{conversation_history}\n"

        # Create comprehensive tutoring question with all context embedded
        tutoring_question = _build_tutoring_question(
            tutoring_data, job.title or "this content", user_message, conversation_context
        )

        # Use the existing vector service to get contextual response
        result = await vector_service.ask_question_about_job(
            user_id=context.user.id, job_id=job_id, question=tutoring_question
        )

        if result["success"]:
            logger.info(
                f"MCP tutor_chat: user={context.user.id}, job={job_id}, message='{user_message[:50]}...'"
            )

            # Update conversation tracking with the new exchange
            if existing_conversation:
                if not existing_conversation.messages:
                    existing_conversation.messages = {"conversation_history": []}
                if "conversation_history" not in existing_conversation.messages:
                    existing_conversation.messages["conversation_history"] = []

                existing_conversation.messages["conversation_history"].append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "user_message": user_message,
                        "tutor_response": result["answer"],
                    }
                )
                existing_conversation.updated_at = datetime.utcnow()
                await context.db_session.commit()

                # Auto-generate summary after every 3 exchanges or at end of intro
                total_exchanges = len(
                    existing_conversation.messages.get("conversation_history", [])
                )
                if total_exchanges % 3 == 0 or total_exchanges == 1:
                    try:
                        await generate_conversation_summary(context, job_id, force_update=True)
                        logger.info(
                            f"Auto-generated summary after {total_exchanges} exchanges for job {job_id}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to auto-generate summary: {e}")

            return {
                "success": True,
                "response": result["answer"],
                "intro_delivered": False,
                "tutoring_data": {
                    "themes": tutoring_data["themes"],
                    "content_type": tutoring_data["content_type"],
                    "available_questions": tutoring_data["discussion_questions"],
                },
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Tutoring response failed"),
                "response": "I'm having trouble accessing the content right now. Please try again.",
            }

    except Exception as e:
        logger.error(f"Error in tutor_chat MCP tool: {e}")
        return {"success": False, "error": f"Tutoring conversation failed: {e!s}", "response": ""}


def _build_tutoring_question(
    tutoring_data: dict, content_title: str, user_message: str, conversation_context: str
) -> str:
    """Build complete tutoring question with embedded instructions (grug-brain approach)."""

    themes_text = ", ".join(tutoring_data["themes"])
    characters_text = ", ".join(
        [f"{char['name']} ({char['role']})" for char in tutoring_data["characters"]]
    )
    setting_text = f"{tutoring_data['setting']['time']} in {tutoring_data['setting']['place']}"

    return f"""I need you to act as an expert Socratic tutor for "{content_title}". 

CONTENT ANALYSIS FOR TUTORING:
- Content Type: {tutoring_data["content_type"]}
- Main Themes: {themes_text}
- Key Characters/Figures: {characters_text}
- Setting/Context: {setting_text}

TUTORING APPROACH - Follow these principles:
1. Use the Socratic method - guide the student to discover insights through questioning
2. Ask probing follow-up questions rather than giving direct answers  
3. Help the student connect ideas to their existing knowledge
4. Encourage critical thinking and analysis
5. Be encouraging and supportive while challenging their understanding
6. Draw on the specific content of this audiobook to support your tutoring

AVAILABLE DISCUSSION STARTERS you can reference:
{chr(10).join(f"- {q}" for q in tutoring_data["discussion_questions"])}

{conversation_context}

STUDENT'S MESSAGE: {user_message}

Please respond as a Socratic tutor, using your knowledge of the audiobook content to guide the student's learning. Ask thoughtful questions, provide insights when appropriate, and help them think deeply about the material."""


async def generate_conversation_summary(
    context: MCPAuthContext, job_id: str, force_update: bool = False
) -> dict[str, Any]:
    """
    Generate a summary of the tutoring conversation for a specific job.

    This function creates a concise summary of the tutoring session including:
    - Whether intro lecture was completed
    - Key topics discussed
    - Student engagement level
    - Learning progress indicators

    Args:
        context: Authentication context with user and database session
        job_id: The job ID to generate summary for
        force_update: Whether to regenerate summary even if one exists

    Returns:
        Dictionary with summary generation results
    """
    try:
        # Get the conversation record
        conversation_result = await context.db_session.execute(
            select(TutorConversation)
            .where(
                TutorConversation.user_id == context.user.id,
                TutorConversation.job_id == job_id,
                TutorConversation.session_type == "socratic",
            )
            .order_by(TutorConversation.created_at.desc())
        )
        conversation = conversation_result.scalar_one_or_none()

        if not conversation:
            return {
                "success": False,
                "error": "No conversation found",
                "message": "No tutoring conversation found for this audiobook.",
            }

        # Check if summary already exists and force_update is False
        if conversation.summary and not force_update:
            return {
                "success": True,
                "summary": conversation.summary,
                "message": "Existing summary retrieved.",
                "generated_new": False,
            }

        # Generate summary based on conversation data
        intro_status = (
            "✅ Opening lecture completed"
            if conversation.is_intro_completed
            else "❌ Opening lecture not delivered"
        )

        conversation_history = (
            conversation.messages.get("conversation_history", []) if conversation.messages else []
        )
        message_count = len(conversation_history)

        if message_count == 0:
            # Only intro was delivered
            summary = f"""Tutoring Session Summary - {datetime.utcnow().strftime("%Y-%m-%d")}

{intro_status}

Session Details:
- Total exchanges: {message_count}
- Status: Introduction only, no dialogue yet
- Duration: Opening lecture presentation

Notes: User received the opening lecture introduction to the content. Ready for Socratic dialogue in future sessions."""
        else:
            # Extract key information from conversation
            recent_topics = []
            for msg in conversation_history[-3:]:  # Last 3 exchanges
                if len(msg.get("user_message", "")) > 10:
                    recent_topics.append(
                        msg["user_message"][:100] + "..."
                        if len(msg["user_message"]) > 100
                        else msg["user_message"]
                    )

            topics_text = "\n- ".join(recent_topics) if recent_topics else "General discussion"

            summary = f"""Tutoring Session Summary - {datetime.utcnow().strftime("%Y-%m-%d")}

{intro_status}

Session Details:
- Total exchanges: {message_count}
- Engagement level: {"High" if message_count > 5 else "Moderate" if message_count > 2 else "Getting started"}
- Session status: Active dialogue

Recent Topics Discussed:
- {topics_text}

Progress: Student is actively engaging with the content through Socratic dialogue. Conversation demonstrates curiosity and critical thinking."""

        # Store the summary
        conversation.summary = summary
        conversation.updated_at = datetime.utcnow()
        await context.db_session.commit()

        logger.info(f"Generated conversation summary for job {job_id}, user {context.user.id}")

        return {
            "success": True,
            "summary": summary,
            "message": "Conversation summary generated successfully.",
            "generated_new": True,
            "conversation_stats": {
                "intro_completed": conversation.is_intro_completed,
                "message_count": message_count,
                "last_updated": conversation.updated_at.isoformat(),
            },
        }

    except Exception as e:
        logger.error(f"Error generating conversation summary: {e}")
        return {
            "success": False,
            "error": f"Summary generation failed: {e!s}",
            "message": "Failed to generate conversation summary.",
        }
