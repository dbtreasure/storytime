"""Voice Assistant WebSocket proxy for OpenAI Realtime API."""

import asyncio
import json
import logging
from typing import Any

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.websockets import WebSocketState

from .auth import get_current_user
from .settings import get_settings
from ..database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice-assistant", tags=["voice-assistant"])


@router.websocket("/realtime")
async def voice_assistant_proxy(websocket: WebSocket):
    """
    WebSocket proxy to OpenAI Realtime API.
    Handles authentication and forwards messages bidirectionally.
    """
    settings = get_settings()
    
    if not settings.openai_api_key:
        await websocket.close(code=1008, reason="OpenAI API key not configured")
        return

    await websocket.accept()
    
    # Authenticate user via token sent in first message
    try:
        auth_message = await websocket.receive_text()
        auth_data = json.loads(auth_message)
        
        if auth_data.get("type") != "auth":
            await websocket.close(code=1008, reason="Authentication required")
            return
            
        token = auth_data.get("token")
        if not token:
            await websocket.close(code=1008, reason="Token required")
            return
            
        # Validate token and get user
        from .auth import verify_token
        logger.info(f"Attempting to verify token: {token[:20]}...")
        current_user = await verify_token(token)
        if not current_user:
            logger.error(f"Token validation failed for token: {token[:20]}...")
            await websocket.close(code=1008, reason="Invalid token")
            return
            
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")
        return
        
    logger.info(f"Voice assistant connection accepted for user {current_user.email}")
    
    # Send authentication success message
    await websocket.send_text(json.dumps({
        "type": "auth.success",
        "user_id": current_user.id
    }))

    openai_ws = None
    try:
        # Connect to OpenAI Realtime API
        openai_url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
        
        openai_ws = await websockets.connect(
            openai_url,
            additional_headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        )
        
        logger.info("Connected to OpenAI Realtime API")

        # Create tasks for bidirectional message forwarding
        client_to_openai_task = asyncio.create_task(
            forward_client_to_openai(websocket, openai_ws, current_user)
        )
        openai_to_client_task = asyncio.create_task(
            forward_openai_to_client(openai_ws, websocket, current_user)
        )

        # Wait for either task to complete (connection closed)
        done, pending = await asyncio.wait(
            [client_to_openai_task, openai_to_client_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"Failed to connect to OpenAI: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": {
                "message": f"Failed to connect to OpenAI: {e.status_code}",
                "type": "connection_error"
            }
        }))
    except Exception as e:
        logger.error(f"Voice assistant error: {e}")
        await websocket.send_text(json.dumps({
            "type": "error", 
            "error": {
                "message": f"Voice assistant error: {str(e)}",
                "type": "internal_error"
            }
        }))
    finally:
        if openai_ws:
            await openai_ws.close()
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


async def forward_client_to_openai(
    client_ws: WebSocket, 
    openai_ws: websockets.WebSocketServerProtocol,
    user: User
):
    """Forward messages from client to OpenAI."""
    try:
        while True:
            # Receive message from client
            try:
                message = await client_ws.receive_text()
                logger.debug(f"Client -> OpenAI: {message[:100]}...")
                
                # Parse and potentially modify message
                try:
                    parsed = json.loads(message)
                    
                    # Log audio buffer messages
                    if parsed.get("type") == "input_audio_buffer.append":
                        audio_data = parsed.get("audio", "")
                        logger.info(f"Forwarding audio buffer: {len(audio_data)} base64 chars, message size: {len(message)} bytes")
                    elif parsed.get("type") == "input_audio_buffer.commit":
                        logger.info("Forwarding audio buffer commit")
                    
                    # Handle tool calls by intercepting and executing them locally
                    if parsed.get("type") == "conversation.item.create":
                        item = parsed.get("item", {})
                        if item.get("type") == "function_call_output":
                            # This is a tool result, forward as-is
                            pass
                    
                    # Forward message to OpenAI
                    await openai_ws.send(message)
                    
                except json.JSONDecodeError:
                    # Forward raw message if not JSON
                    await openai_ws.send(message)
                    
            except WebSocketDisconnect:
                logger.info(f"Client {user.email} disconnected")
                break
                
    except Exception as e:
        logger.error(f"Error forwarding client to OpenAI: {e}")


async def forward_openai_to_client(
    openai_ws: websockets.WebSocketServerProtocol,
    client_ws: WebSocket,
    user: User
):
    """Forward messages from OpenAI to client, handling tool calls."""
    try:
        async for message in openai_ws:
            logger.debug(f"OpenAI -> Client: {message[:100]}...")
            
            try:
                parsed = json.loads(message)
                
                # Handle tool calls
                if parsed.get("type") == "response.output_item.done":
                    item = parsed.get("item", {})
                    if item.get("type") == "function_call":
                        # Execute tool and send result back to OpenAI
                        await handle_tool_call(parsed, openai_ws, user)
                        continue
                    
                # Forward other messages to client
                await client_ws.send_text(message)
                
            except json.JSONDecodeError:
                # Forward raw message if not JSON
                await client_ws.send_text(message)
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("OpenAI connection closed")
    except Exception as e:
        logger.error(f"Error forwarding OpenAI to client: {e}")


async def handle_tool_call(message: dict[str, Any], openai_ws: websockets.WebSocketServerProtocol, user: User):
    """Handle tool execution and send results back."""
    item = message.get("item", {})
    call_id = item.get("call_id")
    name = item.get("name") 
    arguments_str = item.get("arguments", "{}")
    
    try:
        arguments = json.loads(arguments_str)
        logger.info(f"Executing tool call: {name} with args: {arguments}")
        
        # Execute tool via our existing API endpoints
        result = await execute_mcp_tool(name, arguments, user)
        
        # Send tool result back to OpenAI
        tool_result = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output", 
                "call_id": call_id,
                "output": json.dumps(result)
            }
        }
        
        await openai_ws.send(json.dumps(tool_result))
        logger.info(f"Sent tool result to OpenAI for call {call_id}")
        
        # Trigger response generation with audio
        response_create = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"]
            }
        }
        await openai_ws.send(json.dumps(response_create))
        logger.info("Triggered audio response generation")
        
    except Exception as e:
        logger.error(f"Error executing tool call {name}: {e}")
        
        # Send error result
        error_result = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id, 
                "output": json.dumps({
                    "error": f"Tool execution failed: {str(e)}"
                })
            }
        }
        await openai_ws.send_text(json.dumps(error_result))


async def execute_mcp_tool(name: str, arguments: dict[str, Any], user: User) -> dict[str, Any]:
    """Execute MCP tool using our existing services."""
    from ..services.responses_api_service import ResponsesAPIVectorStoreService
    from ..database import AsyncSessionLocal
    from openai import OpenAI
    
    settings = get_settings()
    openai_client = OpenAI(api_key=settings.openai_api_key)
    
    async with AsyncSessionLocal() as db:
        service = ResponsesAPIVectorStoreService(openai_client, db)
        
        if name == "search_library":
            result = await service.search_library(
                user_id=user.id,
                query=arguments["query"],
                max_results=arguments.get("max_results", 10)
            )
            return result
            
        elif name == "search_job":
            result = await service.search_job_content(
                user_id=user.id,
                job_id=arguments["job_id"],
                query=arguments["query"],
                max_results=arguments.get("max_results", 5)
            )
            return result
            
        elif name == "ask_job_question":
            result = await service.ask_question_about_job(
                user_id=user.id,
                job_id=arguments["job_id"],
                question=arguments["question"]
            )
            return result
            
        else:
            raise ValueError(f"Unknown tool: {name}")