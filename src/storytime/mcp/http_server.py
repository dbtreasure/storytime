"""HTTP-based MCP server implementation with proper SSE support."""

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query, Request, Response
from openai import OpenAI
from pydantic import BaseModel
from sse_starlette import EventSourceResponse

from storytime.api.settings import get_settings
from storytime.mcp.auth.jwt_middleware import authenticate_mcp_request, close_auth_context
from storytime.mcp.tools.opening_lecture import opening_lecture
from storytime.mcp.tools.tutor_chat import tutor_chat
from storytime.mcp.tools.xray_lookup import xray_lookup
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)

# Router for HTTP endpoints
router = APIRouter(prefix="/mcp-server", tags=["MCP"])

# Session management for SSE connections
sse_sessions: dict[str, asyncio.Queue] = {}


class SearchParams(BaseModel):
    query: str
    limit: int = 10


class FetchParams(BaseModel):
    id: str


async def get_authenticated_context(request: Request):
    """Get authenticated user context from request."""
    auth_header = request.headers.get("authorization")
    if not auth_header:
        return None

    return await authenticate_mcp_request(auth_header)


@router.get("/sse")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for MCP communication."""

    # Generate unique session ID
    session_id = str(uuid4())
    message_queue = asyncio.Queue()
    sse_sessions[session_id] = message_queue

    async def event_generator():
        """Generate SSE stream for MCP protocol."""
        try:
            # First, send the endpoint URL for the client to POST messages
            endpoint_data = f"/mcp-server/messages?session_id={session_id}"
            yield {"event": "endpoint", "data": endpoint_data}

            # Wait for client initialization - don't send notifications/initialized
            # The client will send this notification after receiving our initialize response

            # Process messages from queue
            while True:
                try:
                    # Wait for messages with timeout for keepalive
                    message = await asyncio.wait_for(message_queue.get(), timeout=30.0)
                    yield {"event": "message", "data": json.dumps(message)}

                except TimeoutError:
                    # Send keepalive
                    keepalive = {
                        "jsonrpc": "2.0",
                        "method": "notifications/progress",
                        "params": {"progressToken": "keepalive", "progress": 1, "total": 1},
                    }
                    yield {"event": "message", "data": json.dumps(keepalive)}

        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            error_msg = {
                "jsonrpc": "2.0",
                "method": "notifications/message",
                "params": {"level": "error", "message": str(e)},
            }
            yield {"event": "message", "data": json.dumps(error_msg)}
        finally:
            # Clean up session
            sse_sessions.pop(session_id, None)

    return EventSourceResponse(event_generator())


@router.post("/messages")
async def mcp_messages_endpoint(request: Request, session_id: str | None = Query(None)):
    """POST endpoint for MCP messages linked to SSE session."""

    # For Streamable HTTP, session_id might be None - handle directly
    # For SSE connections, check if session exists
    is_sse_connection = session_id and session_id in sse_sessions

    try:
        # Parse JSON-RPC request
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        logger.info(f"MCP message received: method={method}, session={session_id}")

        response = None

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "logging": {}},
                    "serverInfo": {"name": "StorytimeTTS-Knowledge", "version": "1.0.0"},
                },
            }

        elif method == "tools/list":
            # Return available tools - all knowledge API endpoints + tutoring tools
            tools = [
                {
                    "name": "search_library",
                    "description": "Search across user's entire audiobook library using the provided query string and returns matching results with excerpts.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find content across all audiobooks",
                            },
                            "max_results": {
                                "type": "integer",
                                "default": 10,
                                "description": "Maximum number of results to return",
                            },
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "search_job",
                    "description": "Search within specific audiobook content by job ID and returns relevant excerpts from that specific book.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "The job ID of the specific audiobook to search within",
                            },
                            "query": {
                                "type": "string",
                                "description": "Search query to find content within the specific audiobook",
                            },
                            "max_results": {
                                "type": "integer",
                                "default": 5,
                                "description": "Maximum number of results to return",
                            },
                        },
                        "required": ["job_id", "query"],
                    },
                },
                {
                    "name": "ask_job_question",
                    "description": "Ask a specific question about an audiobook's content and get an AI-generated answer based on the book's content.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "The job ID of the audiobook to ask about",
                            },
                            "question": {
                                "type": "string",
                                "description": "The question to ask about the audiobook's content",
                            },
                        },
                        "required": ["job_id", "question"],
                    },
                },
                {
                    "name": "tutor_chat",
                    "description": "Engage in Socratic tutoring dialogue about audiobook content using the Socratic method to help users deeply understand and engage with content.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "The job ID of the audiobook to discuss",
                            },
                            "user_message": {
                                "type": "string",
                                "description": "The user's message or question for the tutoring conversation",
                            },
                            "conversation_history": {
                                "type": "string",
                                "default": "",
                                "description": "Previous conversation context for continuity",
                            },
                        },
                        "required": ["job_id", "user_message"],
                    },
                },
                {
                    "name": "xray_lookup",
                    "description": "Provide contextual content lookup similar to Kindle X-ray, answering queries about characters, concepts, settings, and events in audiobook content.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "The job ID of the audiobook to query",
                            },
                            "query": {
                                "type": "string",
                                "description": "The contextual query (e.g., 'Who is Elizabeth?', 'What is happening?')",
                            },
                        },
                        "required": ["job_id", "query"],
                    },
                },
                {
                    "name": "opening_lecture",
                    "description": "Fetch pre-generated opening lecture content for a specific audiobook to introduce the content before Socratic tutoring begins.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "The job ID of the audiobook to get opening lecture for",
                            },
                        },
                        "required": ["job_id"],
                    },
                },
            ]

            response = {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}

        elif method == "tools/call":
            # Handle tool execution
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "search_library":
                result = await handle_search_library_tool(arguments, request)
            elif tool_name == "search_job":
                result = await handle_search_job_tool(arguments, request)
            elif tool_name == "ask_job_question":
                result = await handle_ask_job_question_tool(arguments, request)
            elif tool_name == "tutor_chat":
                result = await handle_tutor_chat_tool(arguments, request)
            elif tool_name == "xray_lookup":
                result = await handle_xray_lookup_tool(arguments, request)
            elif tool_name == "opening_lecture":
                result = await handle_opening_lecture_tool(arguments, request)
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }

            if response is None:  # Tool executed successfully
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
                }

        elif method == "notifications/initialized":
            # Client is notifying us they've initialized - this is correct!
            logger.info("Client initialized successfully")
            # No response needed for notifications (notifications don't have responses)
            response = None

        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }

        # Handle response based on connection type
        if is_sse_connection:
            # Queue response for SSE delivery
            if response:
                await sse_sessions[session_id].put(response)
            # Return 202 Accepted for SSE
            return Response(status_code=202)
        else:
            # Return response directly for Streamable HTTP
            return response

    except Exception as e:
        logger.error(f"MCP request error: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": body.get("id") if "body" in locals() else None,
            "error": {"code": -32603, "message": f"Internal error: {e!s}"},
        }
        # Handle error response based on connection type
        if session_id and session_id in sse_sessions:
            await sse_sessions[session_id].put(error_response)
            return Response(status_code=202)
        else:
            return error_response


async def handle_search_library_tool(arguments: dict[str, Any], request: Request) -> dict[str, Any]:
    """Handle search tool execution."""

    # Get authentication context
    auth_context = await get_authenticated_context(request)
    if not auth_context:
        return {
            "results": [
                {
                    "id": "auth_error",
                    "title": "Authentication Required",
                    "text": "This tool requires authentication. Please authenticate via OAuth to access your audiobook library.",
                    "url": None,
                }
            ]
        }

    try:
        # Get vector store service
        settings = get_settings()
        if not settings.openai_api_key:
            return {
                "results": [
                    {
                        "id": "config_error",
                        "title": "Service Configuration Error",
                        "text": "OpenAI API key not configured. Please contact administrator.",
                        "url": None,
                    }
                ]
            }

        openai_client = OpenAI(api_key=settings.openai_api_key)
        service = ResponsesAPIVectorStoreService(openai_client, auth_context.db_session)

        # Parse search parameters
        query = arguments.get("query")
        max_results = arguments.get("max_results", 10)

        if not query:
            return {
                "results": [
                    {
                        "id": "missing_query",
                        "title": "Missing Query",
                        "text": "Search query is required",
                        "url": None,
                    }
                ]
            }

        # Search user's library using the correct method
        result = await service.search_library(
            user_id=auth_context.user.id, query=query, max_results=max_results
        )

        if not result.get("success"):
            return {
                "results": [
                    {
                        "id": "search_error",
                        "title": "Search Error",
                        "text": f"Search failed: {result.get('error', 'Unknown error')}",
                        "url": None,
                    }
                ]
            }

        # Transform results to MCP format - use the response_text as primary content
        search_results = []

        # If we have response_text, include it as the main result
        response_text = result.get("response_text", "")
        if response_text:
            search_results.append(
                {
                    "id": "library_search_response",
                    "title": f"Search Results for '{query}'",
                    "text": response_text,
                    "url": None,
                }
            )

        # Also include individual search results if available
        for i, item in enumerate(result.get("results", [])):
            search_results.append(
                {
                    "id": f"result_{i}_{item.get('id', 'unknown')}",
                    "title": item.get("title", f"Result {i + 1}"),
                    "text": item.get("text", item.get("content", ""))[:500],  # Limit snippet length
                    "url": item.get("url"),  # Can be None
                }
            )

        # If no results at all, provide a helpful message
        if not search_results:
            search_results.append(
                {
                    "id": "no_results",
                    "title": "No Results Found",
                    "text": f"No content found for query '{query}' in your audiobook library. Try different search terms or check if content has been properly processed.",
                    "url": None,
                }
            )

        return {"results": search_results}

    except Exception as e:
        logger.error(f"Search tool error: {e}")
        return {
            "results": [
                {
                    "id": "internal_error",
                    "title": "Internal Error",
                    "text": f"An internal error occurred while searching: {e!s}",
                    "url": None,
                }
            ]
        }

    finally:
        # Always close database session
        if auth_context:
            await close_auth_context(auth_context)


async def handle_search_job_tool(arguments: dict[str, Any], request: Request) -> dict[str, Any]:
    """Handle job-specific search tool execution."""

    # Get authentication context
    auth_context = await get_authenticated_context(request)
    if not auth_context:
        return {
            "results": [
                {
                    "id": "auth_error",
                    "title": "Authentication Required",
                    "text": "This tool requires authentication. Please authenticate via OAuth to access your audiobook library.",
                    "url": None,
                }
            ]
        }

    try:
        # Get vector store service
        settings = get_settings()
        if not settings.openai_api_key:
            return {
                "results": [
                    {
                        "id": "config_error",
                        "title": "Service Configuration Error",
                        "text": "OpenAI API key not configured. Please contact administrator.",
                        "url": None,
                    }
                ]
            }

        openai_client = OpenAI(api_key=settings.openai_api_key)
        service = ResponsesAPIVectorStoreService(openai_client, auth_context.db_session)

        # Parse search parameters
        job_id = arguments.get("job_id")
        query = arguments.get("query")
        max_results = arguments.get("max_results", 5)

        if not job_id or not query:
            return {
                "results": [
                    {
                        "id": "missing_params",
                        "title": "Missing Parameters",
                        "text": "Both job_id and query are required for job search",
                        "url": None,
                    }
                ]
            }

        # Search within specific job content
        result = await service.search_job_content(
            user_id=auth_context.user.id, job_id=job_id, query=query, max_results=max_results
        )

        if not result.get("success"):
            return {
                "results": [
                    {
                        "id": "search_error",
                        "title": "Job Search Error",
                        "text": f"Job search failed: {result.get('error', 'Unknown error')}",
                        "url": None,
                    }
                ]
            }

        # Transform results to MCP format
        search_results = []

        # If we have response_text, include it as the main result
        response_text = result.get("response_text", "")
        if response_text:
            search_results.append(
                {
                    "id": f"job_search_response_{job_id}",
                    "title": f"Search Results for '{query}' in Job {job_id}",
                    "text": response_text,
                    "url": None,
                }
            )

        # Also include individual search results if available
        for i, item in enumerate(result.get("results", [])):
            search_results.append(
                {
                    "id": f"job_result_{job_id}_{i}_{item.get('id', 'unknown')}",
                    "title": item.get("title", f"Job Result {i + 1}"),
                    "text": item.get("text", item.get("content", ""))[:500],
                    "url": item.get("url"),
                }
            )

        # If no results at all, provide a helpful message
        if not search_results:
            search_results.append(
                {
                    "id": "no_job_results",
                    "title": "No Results Found",
                    "text": f"No content found for query '{query}' in job {job_id}. Try different search terms or verify the job ID.",
                    "url": None,
                }
            )

        return {"results": search_results}

    except Exception as e:
        logger.error(f"Job search tool error: {e}")
        return {
            "results": [
                {
                    "id": "internal_error",
                    "title": "Internal Error",
                    "text": f"An internal error occurred while searching job content: {e!s}",
                    "url": None,
                }
            ]
        }

    finally:
        # Always close database session
        if auth_context:
            await close_auth_context(auth_context)


async def handle_ask_job_question_tool(
    arguments: dict[str, Any], request: Request
) -> dict[str, Any]:
    """Handle ask job question tool execution."""

    # Get authentication context
    auth_context = await get_authenticated_context(request)
    if not auth_context:
        return {
            "results": [
                {
                    "id": "auth_error",
                    "title": "Authentication Required",
                    "text": "This tool requires authentication. Please authenticate via OAuth to access your audiobook library.",
                    "url": None,
                }
            ]
        }

    try:
        # Get vector store service
        settings = get_settings()
        if not settings.openai_api_key:
            return {
                "results": [
                    {
                        "id": "config_error",
                        "title": "Service Configuration Error",
                        "text": "OpenAI API key not configured. Please contact administrator.",
                        "url": None,
                    }
                ]
            }

        openai_client = OpenAI(api_key=settings.openai_api_key)
        service = ResponsesAPIVectorStoreService(openai_client, auth_context.db_session)

        # Parse question parameters
        job_id = arguments.get("job_id")
        question = arguments.get("question")

        if not job_id or not question:
            return {
                "results": [
                    {
                        "id": "missing_params",
                        "title": "Missing Parameters",
                        "text": "Both job_id and question are required",
                        "url": None,
                    }
                ]
            }

        # Ask question about job content
        result = await service.ask_question_about_job(
            user_id=auth_context.user.id, job_id=job_id, question=question
        )

        if not result.get("success"):
            return {
                "results": [
                    {
                        "id": "question_error",
                        "title": "Question Error",
                        "text": f"Question failed: {result.get('error', 'Unknown error')}",
                        "url": None,
                    }
                ]
            }

        # Transform result to MCP format
        answer = result.get("answer", "")
        job_title = result.get("job_title", f"Job {job_id}")

        return {
            "results": [
                {
                    "id": f"job_answer_{job_id}",
                    "title": f"Answer about '{job_title}'",
                    "text": f"Question: {question}\n\nAnswer: {answer}",
                    "url": None,
                }
            ]
        }

    except Exception as e:
        logger.error(f"Ask job question tool error: {e}")
        return {
            "results": [
                {
                    "id": "internal_error",
                    "title": "Internal Error",
                    "text": f"An internal error occurred while asking question: {e!s}",
                    "url": None,
                }
            ]
        }

    finally:
        # Always close database session
        if auth_context:
            await close_auth_context(auth_context)


async def handle_tutor_chat_tool(arguments: dict[str, Any], request: Request) -> dict[str, Any]:
    """Handle tutor chat tool execution."""

    # Get authentication context
    auth_context = await get_authenticated_context(request)
    if not auth_context:
        return {
            "results": [
                {
                    "id": "auth_error",
                    "title": "Authentication Required",
                    "text": "This tool requires authentication. Please authenticate via OAuth to access your audiobook library.",
                    "url": None,
                }
            ]
        }

    try:
        # Parse tutoring parameters
        job_id = arguments.get("job_id")
        user_message = arguments.get("user_message")
        conversation_history = arguments.get("conversation_history", "")

        if not job_id or not user_message:
            return {
                "results": [
                    {
                        "id": "missing_params",
                        "title": "Missing Parameters",
                        "text": "Both job_id and user_message are required for tutoring",
                        "url": None,
                    }
                ]
            }

        # Use the tutor_chat tool
        result = await tutor_chat(
            job_id=job_id,
            user_message=user_message,
            conversation_history=conversation_history,
            context=auth_context,
        )

        if not result.get("success"):
            return {
                "results": [
                    {
                        "id": "tutor_error",
                        "title": "Tutoring Error",
                        "text": f"Tutoring failed: {result.get('error', 'Unknown error')}",
                        "url": None,
                    }
                ]
            }

        # Transform result to MCP format
        tutor_response = result.get("response", "")
        job_title = result.get("job_title", f"Job {job_id}")

        return {
            "results": [
                {
                    "id": f"tutor_response_{job_id}",
                    "title": f"Tutoring Discussion about '{job_title}'",
                    "text": tutor_response,
                    "url": None,
                }
            ]
        }

    except Exception as e:
        logger.error(f"Tutor chat tool error: {e}")
        return {
            "results": [
                {
                    "id": "internal_error",
                    "title": "Internal Error",
                    "text": f"An internal error occurred during tutoring: {e!s}",
                    "url": None,
                }
            ]
        }

    finally:
        # Always close database session
        if auth_context:
            await close_auth_context(auth_context)


async def handle_xray_lookup_tool(arguments: dict[str, Any], request: Request) -> dict[str, Any]:
    """Handle xray lookup tool execution."""

    # Get authentication context
    auth_context = await get_authenticated_context(request)
    if not auth_context:
        return {
            "results": [
                {
                    "id": "auth_error",
                    "title": "Authentication Required",
                    "text": "This tool requires authentication. Please authenticate via OAuth to access your audiobook library.",
                    "url": None,
                }
            ]
        }

    try:
        # Parse xray parameters
        job_id = arguments.get("job_id")
        query = arguments.get("query")

        if not job_id or not query:
            return {
                "results": [
                    {
                        "id": "missing_params",
                        "title": "Missing Parameters",
                        "text": "Both job_id and query are required for X-ray lookup",
                        "url": None,
                    }
                ]
            }

        # Use the xray_lookup tool
        result = await xray_lookup(job_id=job_id, query=query, context=auth_context)

        if not result.get("success"):
            return {
                "results": [
                    {
                        "id": "xray_error",
                        "title": "X-ray Lookup Error",
                        "text": f"X-ray lookup failed: {result.get('error', 'Unknown error')}",
                        "url": None,
                    }
                ]
            }

        # Transform result to MCP format with progress context
        xray_response = result.get("answer", "")
        lookup_type = result.get("lookup_type", "general")
        content_context = result.get("content_context", {})
        job_title = content_context.get("title", f"Job {job_id}")
        spoiler_warning = result.get("spoiler_warning", {})

        # Add spoiler warning if needed
        response_text = xray_response
        if spoiler_warning.get("potential_spoiler"):
            warning_msg = spoiler_warning.get("warning", "")
            suggestion = spoiler_warning.get("suggestion", "")
            response_text = f"⚠️ SPOILER WARNING: {warning_msg}\n"
            if suggestion:
                response_text += f"💡 {suggestion}\n\n"
            response_text += xray_response

        # Add progress context
        if content_context.get("progress_percentage", 0) > 0:
            progress_pct = content_context["progress_percentage"] * 100
            chapter = content_context.get("current_chapter", "Beginning")
            response_text += f"\n\n📖 Your Progress: {progress_pct:.1f}% (Chapter: {chapter})"

        return {
            "results": [
                {
                    "id": f"xray_response_{job_id}_{lookup_type}",
                    "title": f"X-ray Lookup: '{query}' in '{job_title}'",
                    "text": response_text,
                    "url": None,
                }
            ]
        }

    except Exception as e:
        logger.error(f"X-ray lookup tool error: {e}")
        return {
            "results": [
                {
                    "id": "internal_error",
                    "title": "Internal Error",
                    "text": f"An internal error occurred during X-ray lookup: {e!s}",
                    "url": None,
                }
            ]
        }

    finally:
        # Always close database session
        if auth_context:
            await close_auth_context(auth_context)


async def handle_opening_lecture_tool(
    arguments: dict[str, Any], request: Request
) -> dict[str, Any]:
    """Handle opening lecture tool execution."""

    # Get authentication context
    auth_context = await get_authenticated_context(request)
    if not auth_context:
        return {
            "results": [
                {
                    "id": "auth_error",
                    "title": "Authentication Required",
                    "text": "This tool requires authentication. Please authenticate via OAuth to access your audiobook library.",
                    "url": None,
                }
            ]
        }

    try:
        # Parse opening lecture parameters
        job_id = arguments.get("job_id")

        if not job_id:
            return {
                "results": [
                    {
                        "id": "missing_params",
                        "title": "Missing Parameters",
                        "text": "job_id is required for opening lecture retrieval",
                        "url": None,
                    }
                ]
            }

        # Call the opening lecture tool
        result = await opening_lecture(auth_context.db_session, auth_context.user.id, job_id)

        # Format the response based on success/failure
        if result.get("success"):
            lecture_data = result["opening_lecture"]
            return {
                "results": [
                    {
                        "id": "opening_lecture_content",
                        "title": f"Opening Lecture: {result['job_title']}",
                        "text": f"Introduction: {lecture_data['introduction']}\n\nKey Concepts: {lecture_data['key_concepts_overview']}\n\nLearning Objectives: {lecture_data['learning_objectives']}",
                        "url": None,
                        "metadata": {
                            "lecture_duration_minutes": lecture_data["lecture_duration_minutes"],
                            "engagement_questions": lecture_data["engagement_questions"],
                            "extension_topics": lecture_data["extension_topics"],
                            "generated_at": lecture_data.get("generated_at"),
                        },
                    }
                ]
            }
        else:
            return {
                "results": [
                    {
                        "id": "lecture_error",
                        "title": "Opening Lecture Not Available",
                        "text": result.get(
                            "message", "Opening lecture content could not be retrieved"
                        ),
                        "url": None,
                    }
                ]
            }

    except Exception as e:
        logger.error(f"Opening lecture tool error: {e}")
        return {
            "results": [
                {
                    "id": "internal_error",
                    "title": "Internal Error",
                    "text": f"An internal error occurred while retrieving opening lecture: {e!s}",
                    "url": None,
                }
            ]
        }

    finally:
        # Always close database session
        if auth_context:
            await close_auth_context(auth_context)
