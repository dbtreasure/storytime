# OpenAI Realtime API Integration

This document describes the OpenAI Realtime API integration for StorytimeTTS voice assistant capabilities.

## Overview

The `RealtimeVoiceAssistant` class provides a complete integration between:
- **OpenAI Realtime API**: For speech-to-speech voice interactions
- **StorytimeTTS MCP Server**: For accessing user's audiobook library via tools

## Architecture

```
Voice Input → OpenAI Realtime API → Tool Calls → MCP Server → Vector Search → Response
     ↑                                                                           ↓
Audio Output ← Speech Synthesis ← Text Response ← JSON Results ← Audiobook Content
```

## Key Components

### 1. RealtimeVoiceAssistant (`realtime_client.py`)
- Manages WebSocket connection to OpenAI Realtime API
- Handles audio input/output and text interactions
- Routes tool calls to MCP server
- Configures session with StorytimeTTS-specific instructions

### 2. Available Tools
The assistant automatically exposes these MCP tools:

- **`search_library`**: Search across user's entire audiobook library
- **`search_job`**: Search within a specific audiobook by job ID  
- **`ask_job_question`**: Ask questions about audiobook content

### 3. Event Handlers
- `on_transcription_received`: User speech transcription
- `on_response_received`: Assistant text responses
- `on_audio_received`: Assistant audio output

## Usage Example

```python
from storytime.voice_assistant.realtime_client import RealtimeVoiceAssistant

async def main():
    assistant = RealtimeVoiceAssistant(
        openai_api_key="your_openai_key",
        mcp_base_url="http://localhost:8000", 
        mcp_access_token="user_jwt_token"
    )
    
    # Set up event handlers
    assistant.on_transcription_received = lambda text: print(f"User: {text}")
    assistant.on_response_received = lambda text: print(f"Assistant: {text}")
    
    await assistant.connect()
    
    # Send text or audio input
    await assistant.send_text("Search my library for books about productivity")
    
    # Keep connection alive to receive responses
    await asyncio.sleep(10)
    
    await assistant.disconnect()
```

## Demo Script

Run the interactive demo:

```bash
# Set required environment variables
export OPENAI_API_KEY="your_openai_api_key"
export MCP_ACCESS_TOKEN="user_jwt_token"  # Optional for library access

# Run demo
python src/storytime/voice_assistant/demo.py
```

## Testing

Basic integration test:
```bash
python test_realtime_integration.py
```

## Voice Interaction Flow

1. **User speaks** → Audio captured and sent to Realtime API
2. **Speech-to-text** → Whisper transcribes user input
3. **Intent recognition** → GPT-4 determines if library search is needed
4. **Tool execution** → MCP tools called to search audiobook library
5. **Response generation** → GPT-4 creates natural language response
6. **Text-to-speech** → Response converted to audio output

## Configuration

### Session Configuration
- **Model**: `gpt-4o-realtime-preview-2024-10-01`
- **Voice**: `alloy` (configurable)
- **Audio Format**: 16-bit PCM
- **Turn Detection**: Server-side VAD with 200ms silence threshold
- **Tools**: Auto-enabled for library search capabilities

### Instructions
The assistant is configured with context-aware instructions:
- Understands it's helping with audiobook library management
- Uses tools proactively when users ask about their content
- Provides helpful responses about audiobook search results

## Dependencies

New dependencies added for voice integration:
- `websockets>=12.0`: WebSocket client for Realtime API
- `sse-starlette>=1.6.0`: Server-sent events for MCP communication

## Security

- **Authentication**: JWT tokens required for MCP tool access
- **Audio Privacy**: Audio data only sent to OpenAI Realtime API
- **Library Access**: Only authenticated users can search their own content

## Future Enhancements

- **Audio streaming**: Real-time audio playback integration
- **Voice cloning**: Custom voices based on audiobook content
- **Conversation memory**: Persistent chat history across sessions
- **Multi-language**: Support for non-English audiobooks

## Troubleshooting

### Common Issues

1. **WebSocket connection fails**
   - Check OpenAI API key validity
   - Verify network connectivity
   - Ensure using latest model version

2. **MCP tools not working**  
   - Verify MCP server is running on localhost:8000
   - Check JWT token validity
   - Confirm user has audiobook content in library

3. **Audio not playing**
   - Check audio format compatibility
   - Verify audio output device configuration
   - Ensure proper event handler setup

### Debug Mode
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```