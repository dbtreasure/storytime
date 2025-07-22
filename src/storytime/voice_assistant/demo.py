#!/usr/bin/env python3
"""Demo script for Pipecat voice assistant with proper IPv4 configuration."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from storytime.voice_assistant.mcp_client import MCPClient
from storytime.voice_assistant.pipecat_assistant import (
    StandardPipecatManager,
    StandardPipecatVoiceAssistant,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run the Pipecat voice assistant demo."""

    # Get API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return

    # Create MCP client for StorytimeTTS integration
    mcp_client = MCPClient(
        server_url="http://localhost:8000/mcp-server/sse",
        auth_token=os.getenv("MCP_AUTH_TOKEN", "test-token")
    )

    # Create voice assistant with IPv4 configuration
    assistant = StandardPipecatVoiceAssistant(
        openai_api_key=openai_api_key,
        host="127.0.0.1",  # Force IPv4
        port=8766,  # Port configured in Docker
    )

    # Set up event handlers
    def on_connected():
        logger.info("✓ Voice assistant connected and ready")
        logger.info("WebSocket server listening on ws://127.0.0.1:8766")
        logger.info("Connect your client to start talking!")

    def on_disconnected():
        logger.info("Voice assistant disconnected")

    def on_error(error: Exception):
        logger.error(f"Voice assistant error: {error}")

    assistant.on_connected = on_connected
    assistant.on_disconnected = on_disconnected
    assistant.on_error = on_error

    # Create and start the manager
    manager = StandardPipecatManager(assistant)

    try:
        logger.info("Starting Pipecat voice assistant with IPv4 configuration...")
        logger.info("Using OpenAI Realtime API for voice interaction")

        # Start the assistant
        await manager.start()

        # Register MCP client after startup
        try:
            await assistant.register_mcp_client(mcp_client)
            logger.info("✓ MCP client registered successfully")
        except Exception as e:
            logger.warning(f"Failed to register MCP client: {e}")
            logger.info("Continuing without MCP integration")

        # Keep running until interrupted
        logger.info("\nPress Ctrl+C to stop the server\n")

        while manager.is_running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        await manager.stop()
        logger.info("Voice assistant stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
