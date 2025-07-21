"""
Pipecat Voice Assistant using official architecture patterns and best practices.

Based on Pipecat best practices from:
- examples/foundational/19-openai-realtime-beta.py 
- examples/foundational/39a-mcp-run-sse.py
- examples/websocket/server/bot_websocket_server.py
"""

# CRITICAL: Force IPv4-only resolution before importing Pipecat
# This fixes Docker IPv6 binding issues 
import socket
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host in ('localhost', '127.0.0.1'):
        host = '127.0.0.1'
        family = socket.AF_INET  # Force IPv4
    return _original_getaddrinfo(host, port, family, type, proto, flags)
socket.getaddrinfo = _ipv4_only_getaddrinfo

import asyncio
import logging
import os
from typing import Callable

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
# from pipecat.processors.transcript_processor import TranscriptProcessor  # Not available in this version
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
from pipecat.serializers.protobuf import ProtobufFrameSerializer

logger = logging.getLogger(__name__)


class StandardPipecatVoiceAssistant:
    """Standard Pipecat voice assistant using official architecture patterns."""

    def __init__(
        self,
        openai_api_key: str,
        mcp_tools: list | None = None,
        host: str = "0.0.0.0",
        port: int = 7860,
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

    def _default_instructions(self) -> str:
        """Default system instructions for the voice assistant."""
        return """You are a voice assistant for StorytimeTTS, an AI-powered audiobook platform.

You can help users search their audiobook library, find specific content within books, 
and answer questions about their audiobooks.

When users ask about their audiobooks or want to search for specific content, 
use the provided tools to access their library.

Your voice and personality should be warm and engaging, with a friendly tone.
Keep your responses concise and conversational since this is a voice interaction.
One or two sentences at most unless specifically asked to elaborate."""

    async def start(self) -> None:
        """Start the Pipecat voice assistant server."""
        logger.info("Starting StandardPipecatVoiceAssistant.start() method")
        
        # Create WebSocket transport - IPv4-only patching done at module level
        try:
            self.transport = WebsocketServerTransport(
                params=WebsocketServerParams(
                    serializer=ProtobufFrameSerializer(),
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    add_wav_header=False,
                    vad_analyzer=SileroVADAnalyzer(),  # Use proven VAD implementation
                    session_timeout=60 * 5,  # 5 minutes
                    host="127.0.0.1",  # Force IPv4 localhost
                    port=8766,  # Use different port to avoid IPv6 conflicts
                )
            )
            logger.info("WebSocket transport created successfully with IPv4 patch")
        except Exception as e:
            logger.error(f"Failed to create WebSocket transport: {e}")
            raise

        # Create OpenAI Realtime service with proper session configuration
        try:
            session_properties = SessionProperties(
                input_audio_transcription=InputAudioTranscription(),
                turn_detection=TurnDetection(silence_duration_ms=800),
                instructions=self.system_instructions,
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

        # Create transcript processor for logging (skipped - not available in this version)
        # transcript = TranscriptProcessor()

        # Create context aggregator for message handling
        context = OpenAILLMContext(
            messages=[{"role": "user", "content": "Ready to help!"}],
            # tools=self.mcp_tools,  # TODO: Add MCP tools
        )
        context_aggregator = self.llm.create_context_aggregator(context)

        # Create standard Pipecat pipeline
        self.pipeline = Pipeline([
            self.transport.input(),     # Audio input from WebSocket
            context_aggregator.user(),  # User message aggregation
            self.llm,                   # OpenAI Realtime LLM service
            # transcript.user(),        # Transcript processing (skipped)
            context_aggregator.assistant(),  # Assistant response aggregation  
            self.transport.output(),    # Audio output to WebSocket
        ])

        # Create pipeline task
        self.task = PipelineTask(
            self.pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            )
        )

        # Start the pipeline runner
        self.runner = PipelineRunner(handle_sigint=False)
        
        logger.info(f"Starting standard Pipecat voice assistant on {self.host}:{self.port}")
        
        if self.on_connected:
            self.on_connected()
            
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
                logger.info("Successfully registered MCP tools with LLM using official Pipecat patterns")
            else:
                logger.error(f"Failed to register MCP tools: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error registering MCP client: {e}")

    async def register_mcp_functions(self, mcp_functions: dict) -> None:
        """Register MCP functions with the LLM service (legacy method)."""
        if not self.llm:
            raise RuntimeError("LLM service not initialized")
            
        for name, func in mcp_functions.items():
            self.llm.register_function(name, func)
            logger.info(f"Registered MCP function: {name}")


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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
        await self.assistant.stop()
        logger.info("Stopped standard Pipecat assistant task")

    @property
    def is_running(self) -> bool:
        """Check if the assistant is running."""
        return self._running and self._task and not self._task.done()