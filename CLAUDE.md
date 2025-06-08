# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StorytimeTTS is an AI-powered audiobook generation pipeline that transforms classic literature into immersive audiobooks with character-specific voices. The system uses Google Gemini AI for intelligent text parsing and multiple TTS providers (OpenAI, ElevenLabs) for voice generation.

## Development Commands

### Environment Setup
```bash
# Install dependencies using uv (preferred)
uv sync

# Alternative with pip
pip install -e .
```

### Code Quality
```bash
# Lint and format code
ruff check .
ruff format .

# Type checking (if mypy is installed)
mypy src/
```

### Testing
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_parser.py -v
python -m pytest tests/test_full_pipeline.py -v

# Run with coverage
python -m pytest tests/ --cov=src/storytime
```

### Development Server
```bash
# Start FastAPI development server
cd src && python -m storytime.api.main

# Or with uvicorn directly
uvicorn storytime.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker
```bash
# Build and run with docker-compose
docker-compose up --build

# Run individual container
docker build -t storytime .
docker run -p 8000:8000 storytime
```

## Architecture

### Core Workflow Engine (Junjo-based)
The system uses **Junjo** workflow orchestration with two main pipelines:

1. **Chapter Parsing Workflow** (`workflows/chapter_parsing.py`):
   - `LoadTextNode` → `ChunkTextNode` → `PromptConstructionNode` → `GeminiApiNode` → `ParseSegmentsNode` → `MergeSegmentsNode` → `SaveResultsNode`
   - Fully async with OpenTelemetry observability
   - Handles text chunking, Gemini API calls, and JSON parsing

2. **Audio Generation Workflow** (`workflows/audio_generation.py`):
   - Fan-out pattern with parallel `GenerateSegmentAudioNode` execution
   - Thread pool-based parallelism (configurable concurrency)
   - Retry logic with exponential backoff for TTS failures

### Data Models
- **`TextSegment`**: Individual text chunks with speaker, emotion, and voice hints
- **`Chapter`**: Ordered collection of segments
- **`Character`**: Character metadata with voice assignments per TTS provider
- **`CharacterCatalogue`**: Manages all characters across the book
- **`Book`**: Top-level container for chapters and character catalogue

### TTS Infrastructure
- Abstract `TTSProvider` base class with pluggable providers
- `OpenAIProvider` and `ElevenLabsProvider` implementations
- Consistent voice assignment across characters via `VoiceAssigner`

## Data Flow

```
Text Input → Chapter Parsing (Gemini AI) → Character Analysis → Voice Assignment → Audio Generation (TTS) → Audio Post-Processing → Structured Output
```

Output structure:
```
audio_output/provider/chapter_XX/
├── ch01_001_character.mp3 (individual segments)
├── chapter_01_complete.mp3 (stitched)
└── chapter_01_playlist.m3u
```

## Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Gemini API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | No |
| `TTS_PROVIDER` | Provider choice (`openai`/`eleven`) | No (default: `openai`) |
| `TTS_MAX_CONCURRENCY` | Parallel audio jobs | No (default: `8`) |
| `GEMINI_MODEL` | Gemini model name | No (default: `gemini-1.5-pro`) |

## Dependencies

- **Junjo 0.45+**: Workflow orchestration framework
- **Pydantic 2.0+**: Data validation and serialization
- **FastAPI + Uvicorn**: Async web framework
- **OpenTelemetry**: Observability and tracing
- **Google Generative AI**: Gemini API client
- **OpenAI 1.82+**: TTS services
- **ElevenLabs 2.1+**: Alternative TTS provider
- **Pydub**: Audio processing (requires ffmpeg)

## Project Management (Linear)

### Linear Workspace Information
- **Team ID**: `f8b5f9b8-ae25-42e8-8a4a-cc36fa1923e4` (core team)
- **Team Name**: "core"
- **Primary Project**: "MVP Story Book Launch" 
- **Project ID**: `713a09ee-dceb-4a37-909b-5395c01a68ba`
- **Workspace**: Leviathan LAM (`https://linear.app/leviathan-lam`)

### Issue Management Guidelines
- **Prefix**: All issues use `CORE-XX` identifier format
- **Priority Levels**: 1 (Urgent), 2 (High), 3 (Medium), 4 (Low)
- **Default Priority**: Medium (3) for most feature work
- **Git Branches**: Auto-generated as `dbtreasure/core-XX-issue-title-kebab-case`

### Current Focus Areas
- Unified job management system (CORE-48)
- Content analyzer improvements (CORE-52)
- Junjo workflow integration and observability
- TTS pipeline optimization and multi-voice processing

## Important Notes

- **Audio Requirements**: ffmpeg must be installed for audio processing
- **Observability**: Comprehensive OpenTelemetry tracing with Braintrust integration
- **Error Handling**: Built-in retry logic with exponential backoff for API failures
- **Concurrency**: Configurable parallelism for both text parsing and audio generation
- **Cost Awareness**: Monitor Gemini and TTS API usage as costs scale with content length