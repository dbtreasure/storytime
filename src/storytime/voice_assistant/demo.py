#!/usr/bin/env python3
"""Demo script for testing OpenAI Realtime API with MCP integration."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from storytime.voice_assistant.realtime_client import RealtimeVoiceAssistant

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_text_interaction():
    """Demo text-based interaction with the voice assistant."""
    
    # Get API keys from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable required")
        return
    
    # Optional MCP integration (requires JWT token)
    mcp_token = os.getenv("MCP_ACCESS_TOKEN")  # James Joyce's token for testing
    
    assistant = RealtimeVoiceAssistant(
        openai_api_key=openai_api_key,
        mcp_base_url="http://localhost:8000",
        mcp_access_token=mcp_token
    )
    
    # Set up event handlers
    def on_transcription(transcript: str):
        logger.info(f"User said: {transcript}")
    
    def on_response_text(text: str):
        print(text, end="", flush=True)
    
    def on_audio_received(audio: bytes):
        logger.info(f"Received {len(audio)} bytes of audio")
    
    assistant.on_transcription_received = on_transcription
    assistant.on_response_received = on_response_text
    assistant.on_audio_received = on_audio_received
    
    try:
        await assistant.connect()
        logger.info("Connected to voice assistant")
        
        # Test basic conversation
        print("\n=== Testing basic conversation ===")
        await assistant.send_text("Hello! Can you help me with my audiobook library?")
        await asyncio.sleep(3)  # Wait for response
        
        # Test library search (if MCP is connected)
        if mcp_token:
            print("\n\n=== Testing library search ===")
            await assistant.send_text("Search my library for content about luck")
            await asyncio.sleep(5)  # Wait for tool execution and response
            
            print("\n\n=== Testing job-specific search ===")
            await assistant.send_text("Search within my book for information about creating opportunities")
            await asyncio.sleep(5)
            
            print("\n\n=== Testing question asking ===")
            await assistant.send_text("What are the main ideas about luck in my audiobook?")
            await asyncio.sleep(5)
        else:
            logger.warning("No MCP token provided - skipping library search tests")
            
        print("\n\n=== Demo complete ===")
        
    except Exception as e:
        logger.error(f"Demo error: {e}")
    finally:
        await assistant.disconnect()


async def demo_audio_interaction():
    """Demo audio-based interaction (requires audio input)."""
    logger.info("Audio demo not implemented - would require audio capture setup")


if __name__ == "__main__":
    print("StorytimeTTS Voice Assistant Demo")
    print("=" * 40)
    
    # Check for required environment variables
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set:")
        for var in missing_vars:
            print(f"  export {var}=your_key_here")
        sys.exit(1)
    
    # Optional MCP token
    if not os.getenv("MCP_ACCESS_TOKEN"):
        print("Note: MCP_ACCESS_TOKEN not set - library search features will be unavailable")
        print("To test with MCP integration, set:")
        print("  export MCP_ACCESS_TOKEN=your_jwt_token_here")
        print()
    
    try:
        asyncio.run(demo_text_interaction())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        sys.exit(1)