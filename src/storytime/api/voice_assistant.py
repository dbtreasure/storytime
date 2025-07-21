"""Pipecat Voice Assistant API using official architecture and best practices."""

import asyncio
import logging
from typing import Dict

from fastapi import APIRouter, HTTPException

from ..database import User
from ..voice_assistant.pipecat_assistant import (
    StandardPipecatVoiceAssistant,
    StandardPipecatManager,
)
from ..voice_assistant.pipecat_mcp_integration import create_mcp_integration
from .auth import verify_token
from .settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice-assistant", tags=["voice-assistant"])

# Global manager for the standard Pipecat assistant
_assistant_manager: StandardPipecatManager | None = None
_mcp_functions: Dict[str, callable] = {}
_mcp_client = None


async def _initialize_assistant():
    """Initialize the Pipecat voice assistant with MCP integration."""
    global _assistant_manager, _mcp_functions, _mcp_client
    
    if _assistant_manager and _assistant_manager.is_running:
        logger.info("Standard Pipecat assistant already running")
        return
    
    settings = get_settings()
    
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    # Initialize MCP integration
    try:
        _mcp_client, _mcp_functions = await create_mcp_integration(
            mcp_base_url="http://localhost:8000",
            mcp_access_token="system"  # Use system token for MCP access
        )
        logger.info("MCP integration initialized successfully")
    except Exception as e:
        logger.warning(f"MCP integration failed: {e}")
        _mcp_functions = {}
    
    # Create standard Pipecat assistant
    try:
        assistant = StandardPipecatVoiceAssistant(
            openai_api_key=settings.openai_api_key,
            host="0.0.0.0",
            port=7860,  # Different port to avoid conflicts
            system_instructions="""You are a voice assistant for StorytimeTTS, an AI-powered audiobook platform.

You can help users search their audiobook library, find specific content within books, 
and answer questions about their audiobooks.

Available tools:
- search_library: Search across user's entire audiobook library
- search_job: Search within a specific audiobook by job ID  
- ask_job_question: Ask questions about specific audiobook content

Your voice should be warm, engaging, and conversational.
Keep responses concise since this is voice interaction - one or two sentences unless asked to elaborate."""
        )
        logger.info("StandardPipecatVoiceAssistant created successfully")
    except Exception as e:
        logger.error(f"Failed to create StandardPipecatVoiceAssistant: {e}")
        raise
    
    # Create and start manager first
    _assistant_manager = StandardPipecatManager(assistant)
    await _assistant_manager.start()
    
    # Wait for LLM service to be initialized (assistant.start() runs in background)
    import asyncio
    for i in range(10):  # Wait up to 5 seconds
        if assistant.llm is not None:
            logger.info("LLM service is ready")
            break
        await asyncio.sleep(0.5)
    else:
        logger.warning("LLM service initialization timeout")
    
    # Register MCP client after assistant is started (when LLM service is initialized)
    if _mcp_client:
        await assistant.register_mcp_client(_mcp_client)
    elif _mcp_functions:
        # Fallback to legacy method if available
        await assistant.register_mcp_functions(_mcp_functions)
    
    logger.info("Standard Pipecat assistant initialized and started")


@router.post("/start")
async def start_assistant():
    """Start the standard Pipecat voice assistant."""
    try:
        await _initialize_assistant()
        return {
            "status": "started", 
            "message": "Standard Pipecat assistant started successfully",
            "websocket_url": "ws://localhost:8766",  # Use actual Pipecat server port
            "mcp_integration": "enabled" if _mcp_client else "disabled",
            "mcp_functions": list(_mcp_functions.keys()) if _mcp_functions else []
        }
    except Exception as e:
        logger.error(f"Failed to start assistant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start assistant: {str(e)}")


@router.post("/stop")
async def stop_assistant():
    """Stop the standard Pipecat voice assistant."""
    global _assistant_manager
    
    if _assistant_manager:
        await _assistant_manager.stop()
        _assistant_manager = None
        
    return {
        "status": "stopped",
        "message": "Standard Pipecat assistant stopped successfully"
    }


@router.get("/status")
async def get_status():
    """Get the status of the standard Pipecat assistant."""
    global _assistant_manager
    
    is_running = _assistant_manager and _assistant_manager.is_running
    
    return {
        "status": "running" if is_running else "stopped",
        "websocket_url": "ws://localhost:8766" if is_running else None,  # Use actual Pipecat server port
        "mcp_functions": list(_mcp_functions.keys()) if _mcp_functions else [],
        "architecture": "Standard Pipecat with official components"
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Standard Pipecat Voice Assistant API",
        "version": "1.0.0"
    }