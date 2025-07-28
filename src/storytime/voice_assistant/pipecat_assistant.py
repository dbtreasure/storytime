"""
Pipecat Voice Assistant using official architecture patterns and best practices.

Based on Pipecat best practices from:
- examples/foundational/19-openai-realtime-beta.py
- examples/foundational/39a-mcp-run-sse.py
- examples/websocket/server/bot_websocket_server.py
"""

import asyncio
import contextlib
import json
import logging
import re
from collections.abc import Callable

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.openai_realtime_beta import (
    InputAudioTranscription,
    OpenAIRealtimeBetaLLMService,
    SessionProperties,
    TurnDetection,
)
from pipecat.transports.network.websocket_server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)

logger = logging.getLogger(__name__)


class StandardPipecatVoiceAssistant:
    """Standard Pipecat voice assistant using official architecture patterns."""

    def __init__(
        self,
        openai_api_key: str,
        mcp_tools: list | None = None,
        host: str = "0.0.0.0",  # Bind to all interfaces
        port: int = 8765,  # Standard Pipecat WebSocket port
        system_instructions: str | None = None,
    ):
        self.openai_api_key = openai_api_key
        self.mcp_tools = mcp_tools or []
        self.host = host
        self.port = port
        self.system_instructions = system_instructions or self._default_instructions()

        # Pipeline components
        self.transport: WebsocketServerTransport | None = None
        self.llm: OpenAIRealtimeBetaLLMService | None = None
        self.pipeline: Pipeline | None = None
        self.task: PipelineTask | None = None
        self.runner: PipelineRunner | None = None

        # Event callbacks
        self.on_connected: Callable[[], None] | None = None
        self.on_disconnected: Callable[[], None] | None = None
        self.on_error: Callable[[Exception], None] | None = None

    def _get_initial_conversation(self) -> list[dict]:
        """Get initial conversation to trigger tutoring flow if in tutor mode."""
        # Check if this is a tutoring session by looking for tutoring context in instructions
        if (
            "TUTORING CONTEXT" in self.system_instructions
            and "CRITICAL: This is a tutoring session" in self.system_instructions
        ):
            # Extract job ID from system instructions
            job_id_match = re.search(r"Job ID: ([a-f0-9\-]+)", self.system_instructions)
            if job_id_match:
                job_id = job_id_match.group(1)
                # Return initial conversation that forces tutor_chat call
                return [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Hello, I'm ready to start our tutoring session.",
                            }
                        ],
                    },
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_initial_tutor",
                                "type": "function",
                                "function": {
                                    "name": "tutor_chat",
                                    "arguments": json.dumps(
                                        {
                                            "job_id": job_id,
                                            "user_message": "Hello, I'm ready to start our tutoring session.",
                                        }
                                    ),
                                },
                            }
                        ],
                    },
                ]
        return []  # No initial conversation for non-tutoring modes

    def _get_tool_choice(self) -> str:
        """Get tool choice configuration - force tool usage in tutoring mode."""
        # Use auto for now to debug tool availability
        return "auto"

    def _default_instructions(self) -> str:
        """Default system instructions for the voice assistant, built dynamically from available tools."""

        # Tool descriptions that match the MCP server definitions
        tool_descriptions = {
            "search_library": "Search across the user's entire audiobook library",
            "search_job": "Search within specific audiobook content by job ID",
            "ask_job_question": "Ask questions about specific audiobook content",
            "tutor_chat": "Engage in Socratic tutoring dialogue about audiobook content",
            "xray_lookup": "Provide contextual content lookup (characters, concepts, settings)",
            "opening_lecture": "Fetch pre-generated opening lecture content to introduce audiobooks before tutoring",
        }

        # Tool usage examples
        tool_examples = {
            "search_library": [
                '"What books do I have?" → use search_library',
                '"Do I have any books about science?" → use search_library with "science"',
                '"Search for books by Shakespeare" → use search_library with "Shakespeare"',
            ],
            "search_job": ['"Search within this specific book" → use search_job with job ID'],
            "ask_job_question": ['"What is this book about?" → use ask_job_question'],
            "tutor_chat": [
                '"Help me understand this book better" → use tutor_chat for Socratic dialogue',
                '"Teach me about the themes in this book" → use tutor_chat',
            ],
            "xray_lookup": [
                '"Who is this character?" → use xray_lookup for contextual information',
                '"What does this concept mean?" → use xray_lookup',
            ],
            "opening_lecture": [
                '"Give me an introduction to this book" → use opening_lecture to provide prepared lecture content',
                '"Start with an overview" → use opening_lecture at the beginning of tutoring sessions',
            ],
        }

        # Build tools list dynamically (all tools should be available)
        available_tools = list(tool_descriptions.keys())
        tools_text = "\n".join([f"- {tool}: {tool_descriptions[tool]}" for tool in available_tools])

        # Build examples dynamically
        examples = []
        for tool in available_tools:
            examples.extend(tool_examples.get(tool, []))
        examples_text = "\n".join([f"- {example}" for example in examples])

        return f"""You are a voice assistant for StorytimeTTS, an AI-powered audiobook platform.

You have access to the following tools to help users:
{tools_text}

TUTORING SESSION PROTOCOL:
When users are in tutoring mode, follow this flow:

1. IMMEDIATE FIRST ACTION: If system instructions contain "CRITICAL: This is a tutoring session", you MUST call tutor_chat as your very first response without waiting for user input. The tutor_chat tool will automatically:
   - Check the database for existing conversations
   - If no intro has been delivered, fetch and present the opening lecture content
   - Mark the intro as completed for future sessions
   - Handle all conversation tracking in the database

2. EVERY INTERACTION: Use tutor_chat for ALL tutoring interactions:
   - First time: Delivers opening lecture automatically, then ready for dialogue
   - Subsequent times: Goes straight to Socratic dialogue
   - Handles interruptions and user preferences naturally
   - Tracks all conversation history in database

3. NEVER call opening_lecture directly - tutor_chat handles everything automatically

GENERAL TOOL USAGE:
When users ask about their audiobooks, search for books, or want to find specific content,
you MUST use the appropriate tools. Always search their library first before saying you don't know.

Examples of when to use tools:
{examples_text}

VOICE INTERACTION GUIDELINES:
- Keep responses concise and conversational for voice interaction
- Use natural speech patterns and pauses
- Be warm, engaging, and encouraging
- Respond immediately to interruptions with acknowledgment
- For tutoring: Guide discovery through questions rather than lecturing (except during opening lecture)
- Always be ready to pivot based on user needs and interruptions"""

    async def start(self) -> None:
        """Start the Pipecat voice assistant server."""
        logger.info("Starting StandardPipecatVoiceAssistant.start() method")

        # Create WebSocket transport
        self.transport = WebsocketServerTransport(
            params=WebsocketServerParams(
                serializer=ProtobufFrameSerializer(),
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
            ),
            host="0.0.0.0",  # Bind to all interfaces for Docker
            port=self.port,
        )
        logger.info(f"WebSocket transport created successfully on 0.0.0.0:{self.port}")

        # Define tools for OpenAI Realtime session
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
                            "description": "Search query to find audiobooks in the library",
                        }
                    },
                    "required": ["query"],
                },
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
                            "description": "Job ID of the specific audiobook to search within",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query to find content within the book",
                        },
                    },
                    "required": ["job_id", "query"],
                },
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
                            "description": "Job ID of the audiobook to ask about",
                        },
                        "question": {
                            "type": "string",
                            "description": "Question to ask about the audiobook content",
                        },
                    },
                    "required": ["job_id", "question"],
                },
            },
            {
                "type": "function",
                "name": "tutor_chat",
                "description": "Engage in Socratic tutoring dialogue about audiobook content using the Socratic method to help users deeply understand and engage with content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "Job ID of the audiobook to discuss",
                        },
                        "user_message": {
                            "type": "string",
                            "description": "The user's message or question for the tutoring conversation",
                        },
                        "conversation_history": {
                            "type": "string",
                            "description": "Previous conversation context for continuity",
                        },
                    },
                    "required": ["job_id", "user_message"],
                },
            },
            {
                "type": "function",
                "name": "xray_lookup",
                "description": "Provide contextual content lookup similar to Kindle X-ray, answering queries about characters, concepts, settings, and events in audiobook content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "Job ID of the audiobook to query",
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
                "type": "function",
                "name": "opening_lecture",
                "description": "Fetch pre-generated opening lecture content for a specific audiobook to introduce the content before Socratic tutoring begins.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "Job ID of the audiobook to get opening lecture for",
                        }
                    },
                    "required": ["job_id"],
                },
            },
        ]

        # Create OpenAI Realtime service with proper session configuration
        try:
            session_properties = SessionProperties(
                input_audio_transcription=InputAudioTranscription(model="whisper-1"),
                turn_detection=TurnDetection(
                    type="server_vad",
                    threshold=0.5,
                    prefix_padding_ms=300,
                    silence_duration_ms=1200,  # Increase to reduce interruption sensitivity
                ),
                instructions=f"{self.system_instructions}\n\nIMPORTANT: Always respond with audio. Keep responses conversational and concise.",
                voice="alloy",  # Explicitly set voice for audio output
                input_audio_format="pcm16",
                output_audio_format="pcm16",
                modalities=["text", "audio"],  # Enable both text and audio
                tool_choice=self._get_tool_choice(),  # Force tutor_chat in tutoring mode
                tools=tools,  # Add tools to OpenAI session
                # Add initial conversation to trigger tutoring flow if needed
                # conversation=self._get_initial_conversation()  # Temporarily disabled to restore audio
            )

            self.llm = OpenAIRealtimeBetaLLMService(
                api_key=self.openai_api_key,
                session_properties=session_properties,
                start_audio_paused=False,
            )

            logger.info("OpenAI Realtime service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI Realtime service: {e}")
            raise

        # MCP tools will be registered after the client is available
        self._tools_schema = None

        # Create context aggregator for message handling
        # Check if this is a tutoring session and inject appropriate initial message
        initial_message = "Ready to help!"
        if "CRITICAL: This is a tutoring session" in self.system_instructions:
            initial_message = "Hello, I'm ready to start our tutoring session."

        context = OpenAILLMContext(
            messages=[{"role": "user", "content": initial_message}],
        )
        context_aggregator = self.llm.create_context_aggregator(context)

        # Create standard Pipecat pipeline with debugging
        self.pipeline = Pipeline(
            [
                self.transport.input(),  # Audio input from WebSocket
                context_aggregator.user(),  # User message aggregation
                self.llm,  # OpenAI Realtime LLM service
                context_aggregator.assistant(),  # Assistant response aggregation
                self.transport.output(),  # Audio output to WebSocket
            ]
        )

        logger.info(
            "Pipeline created with components: input -> user_context -> llm -> assistant_context -> output"
        )

        # Create pipeline task
        self.task = PipelineTask(
            self.pipeline,
            params=PipelineParams(
                allow_interruptions=True,  # Enable interruptions for natural conversation
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

        # Register WebSocket event handlers
        @self.transport.event_handler("on_websocket_ready")
        async def on_websocket_ready(transport):
            logger.info(f"WebSocket server ready and listening on 0.0.0.0:{self.port}")
            if self.on_connected:
                self.on_connected()

        @self.transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info(f"Client connected from {client.remote_address}")
            # Kick off the conversation when client connects
            await self.task.queue_frames([context_aggregator.user().get_context_frame()])

        @self.transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info(f"Client disconnected from {client.remote_address}")
            await self.task.cancel()

        # Start the pipeline runner
        self.runner = PipelineRunner(handle_sigint=False)

        logger.info("Starting standard Pipecat voice assistant...")

        try:
            await self.runner.run(self.task)
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            if self.on_error:
                self.on_error(e)
            raise

    async def stop(self) -> None:
        """Stop the voice assistant."""
        if self.runner:
            await self.runner.cancel()

        if self.on_disconnected:
            self.on_disconnected()

        logger.info("Standard Pipecat voice assistant stopped")

    async def register_mcp_client(self, mcp_client) -> None:
        """Register MCP client with the LLM service using official Pipecat patterns."""
        if not self.llm:
            raise RuntimeError("LLM service not initialized")

        if not mcp_client:
            logger.warning("No MCP client provided")
            return

        try:
            # Use official Pipecat method to register MCP tools
            from .pipecat_mcp_integration import register_mcp_tools_with_llm

            result = await register_mcp_tools_with_llm(mcp_client, self.llm)

            if result.get("success"):
                self._tools_schema = result.get("tools_schema")
                logger.info(
                    "Successfully registered MCP tools with LLM using official Pipecat patterns"
                )

            else:
                logger.error(f"Failed to register MCP tools: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error registering MCP client: {e}")


class StandardPipecatManager:
    """Manager for running the standard Pipecat assistant in a separate task."""

    def __init__(self, assistant: StandardPipecatVoiceAssistant):
        self.assistant = assistant
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the assistant in a background task."""
        if self._running:
            logger.warning("Assistant already running")
            return

        self._running = True
        self._task = asyncio.create_task(self.assistant.start())
        logger.info("Started standard Pipecat assistant task")

    async def stop(self) -> None:
        """Stop the assistant task."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        await self.assistant.stop()
        logger.info("Stopped standard Pipecat assistant task")

    @property
    def is_running(self) -> bool:
        """Check if the assistant is running."""
        return self._running and self._task and not self._task.done()
