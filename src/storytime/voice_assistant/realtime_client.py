"""OpenAI Realtime API client for voice assistant integration."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable
from uuid import uuid4

import websockets
from websockets.client import WebSocketClientProtocol

from storytime.voice_assistant.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class RealtimeVoiceAssistant:
    """OpenAI Realtime API client with MCP tool integration."""

    def __init__(
        self,
        openai_api_key: str,
        mcp_base_url: str = "http://localhost:8000",
        mcp_access_token: str | None = None,
    ) -> None:
        self.openai_api_key = openai_api_key
        self.mcp_base_url = mcp_base_url
        self.mcp_access_token = mcp_access_token
        
        self.ws: WebSocketClientProtocol | None = None
        self.mcp_client: MCPClient | None = None
        self.session_id: str | None = None
        
        # Event handlers
        self.on_audio_received: Callable[[bytes], None] | None = None
        self.on_transcription_received: Callable[[str], None] | None = None
        self.on_response_received: Callable[[str], None] | None = None

    async def connect(self) -> None:
        """Connect to OpenAI Realtime API and MCP server."""
        
        # Connect to MCP server if access token is provided
        if self.mcp_access_token:
            self.mcp_client = MCPClient(self.mcp_base_url, self.mcp_access_token)
            await self.mcp_client.connect()
            logger.info("Connected to MCP server")

        # Connect to OpenAI Realtime API
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
        
        self.ws = await websockets.connect(url, extra_headers=headers)
        logger.info("Connected to OpenAI Realtime API")
        
        # Start session and configure it
        await self._initialize_session()
        
        # Start listening for messages
        asyncio.create_task(self._listen_for_messages())

    async def _initialize_session(self) -> None:
        """Initialize the Realtime session with tools and configuration."""
        
        # Get available MCP tools if connected
        tools = []
        if self.mcp_client:
            tools = [
                {
                    "type": "function",
                    "name": "search_library",
                    "description": "Search across user's entire audiobook library using the provided query string and returns matching results with excerpts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find content across all audiobooks"
                            },
                            "max_results": {
                                "type": "integer",
                                "default": 10,
                                "description": "Maximum number of results to return"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "type": "function",
                    "name": "search_job",
                    "description": "Search within specific audiobook content by job ID and returns relevant excerpts from that specific book.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "The job ID of the specific audiobook to search within"
                            },
                            "query": {
                                "type": "string",
                                "description": "Search query to find content within the specific audiobook"
                            },
                            "max_results": {
                                "type": "integer",
                                "default": 5,
                                "description": "Maximum number of results to return"
                            }
                        },
                        "required": ["job_id", "query"]
                    }
                },
                {
                    "type": "function",
                    "name": "ask_job_question",
                    "description": "Ask a specific question about an audiobook's content and get an AI-generated answer based on the book's content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "The job ID of the audiobook to ask about"
                            },
                            "question": {
                                "type": "string",
                                "description": "The question to ask about the audiobook's content"
                            }
                        },
                        "required": ["job_id", "question"]
                    }
                }
            ]

        # Send session update with tool configuration
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": (
                    "You are a voice assistant for StorytimeTTS, an AI-powered audiobook platform. "
                    "You can help users search their audiobook library, find specific content within books, "
                    "and answer questions about their audiobooks. "
                    "When users ask about their audiobooks or want to search for specific content, "
                    "use the provided tools to access their library."
                ),
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 200
                },
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.8,
                "max_response_output_tokens": 4096
            }
        }
        
        await self._send_message(session_update)

    async def _send_message(self, message: dict[str, Any]) -> None:
        """Send a message to the Realtime API."""
        if self.ws:
            await self.ws.send(json.dumps(message))

    async def _listen_for_messages(self) -> None:
        """Listen for messages from the Realtime API."""
        if not self.ws:
            return

        try:
            async for raw_message in self.ws:
                try:
                    message = json.loads(raw_message)
                    await self._handle_message(message)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode message: {raw_message}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        except Exception as e:
            logger.error(f"Error in message listener: {e}")

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle incoming messages from the Realtime API."""
        message_type = message.get("type")
        
        if message_type == "session.created":
            self.session_id = message.get("session", {}).get("id")
            logger.info(f"Session created: {self.session_id}")
            
        elif message_type == "conversation.item.input_audio_transcription.completed":
            transcript = message.get("transcript", "")
            if self.on_transcription_received:
                self.on_transcription_received(transcript)
                
        elif message_type == "response.audio.delta":
            audio_data = message.get("delta", "")
            if audio_data and self.on_audio_received:
                # Convert base64 audio to bytes
                import base64
                audio_bytes = base64.b64decode(audio_data)
                self.on_audio_received(audio_bytes)
                
        elif message_type == "response.text.delta":
            text_delta = message.get("delta", "")
            if text_delta and self.on_response_received:
                self.on_response_received(text_delta)
                
        elif message_type == "response.function_call_arguments.delta":
            # Tool call in progress
            call_id = message.get("call_id")
            delta = message.get("delta", "")
            logger.info(f"Function call delta for {call_id}: {delta}")
            
        elif message_type == "response.function_call_arguments.done":
            # Tool call complete, execute it
            await self._execute_tool_call(message)
            
        elif message_type == "error":
            error = message.get("error", {})
            logger.error(f"Realtime API error: {error}")

    async def _execute_tool_call(self, message: dict[str, Any]) -> None:
        """Execute a tool call via MCP and return the result."""
        if not self.mcp_client:
            logger.error("Tool call requested but MCP client not connected")
            return

        call_id = message.get("call_id")
        name = message.get("name")
        arguments_str = message.get("arguments", "{}")
        
        try:
            arguments = json.loads(arguments_str)
            logger.info(f"Executing tool call: {name} with args: {arguments}")
            
            # Execute tool via MCP
            await self.mcp_client.call_tool(name, arguments)
            
            # Wait for the result from MCP
            async for mcp_message in self.mcp_client.iter_messages():
                if mcp_message.get("id") == self.mcp_client._request_id:
                    result = mcp_message.get("result", {})
                    
                    # Send tool result back to Realtime API
                    tool_result = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(result)
                        }
                    }
                    
                    await self._send_message(tool_result)
                    
                    # Trigger response generation
                    response_create = {
                        "type": "response.create",
                        "response": {
                            "modalities": ["text", "audio"]
                        }
                    }
                    await self._send_message(response_create)
                    break
                    
        except Exception as e:
            logger.error(f"Error executing tool call {name}: {e}")
            
            # Send error result
            error_result = {
                "type": "conversation.item.create", 
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps({
                        "error": f"Tool execution failed: {e}"
                    })
                }
            }
            await self._send_message(error_result)

    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data to the Realtime API."""
        import base64
        
        audio_b64 = base64.b64encode(audio_data).decode()
        
        message = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }
        
        await self._send_message(message)

    async def send_text(self, text: str) -> None:
        """Send text input to the Realtime API."""
        message = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": text
                    }
                ]
            }
        }
        
        await self._send_message(message)
        
        # Trigger response
        response_create = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"]
            }
        }
        await self._send_message(response_create)

    async def disconnect(self) -> None:
        """Disconnect from both APIs."""
        if self.mcp_client:
            await self.mcp_client.disconnect()
            
        if self.ws:
            await self.ws.close()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()