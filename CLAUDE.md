# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StorytimeTTS is an AI-powered audiobook generation platform that transforms text content into high-quality audiobooks. The system has evolved from complex multi-voice character processing to a streamlined, unified job management platform supporting both simple text-to-audio conversion and intelligent book processing with automatic chapter detection and parallel processing.

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

## Delegate-to-Codex Policy

When encountering any code-related task—whether large features, minor fixes, tests, CI setup, or code cleanup—use OpenAI Codex:

1. On receiving a coding task:
   - Prompt: “Delegating coding tasks to Codex.”
   - Trigger `codex` CLI in `full-auto` or `auto-edit` mode.
2. Provide:
   - The user’s original instructions.
   - Key project context (files, style guides, domains).
3. Let Codex:
   - Read/write files.
   - Run tests, linters, and shell commands in sandbox.
   - Produce diffs, logs, and results.
4. Capture Codex output:
   - Display patch diffs, test outcomes, shell logs.
   - If approval needed, show options and ask user.
5. After Codex finishes:
   - Summarize changes for the user.
   - Ask: “Merge these changes into main/branch?”

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

### Current System Architecture
The system has evolved to a **unified job management platform** with intelligent content processing:

#### **1. FastAPI-based REST API**
- **Jobs API** (`/api/v1/jobs/`): Complete job lifecycle management
- **Audio Streaming API** (`/api/v1/audio/`): Streaming with resume support
- **Progress Tracking API** (`/api/v1/progress/`): Resume functionality
- **Authentication API** (`/api/v1/auth/`): JWT-based user management

#### **2. Core Services**
- **Job Processor**: Unified processing with step-by-step tracking
- **Book Analyzer**: Intelligent chapter detection and structure analysis
- **Book Processor**: Full book workflow with parallel chapter processing
- **TTS Generator**: Simplified single-voice TTS with smart chunking

#### **3. Data Architecture**
- **Job Management**: Flexible job types (text-to-audio, book processing, multi-voice)
- **Step Tracking**: Granular progress monitoring and error handling
- **User Management**: JWT authentication with bcrypt password hashing
- **Progress Tracking**: Resume functionality with chapter-level tracking

#### **4. Infrastructure**
- **DigitalOcean Spaces**: Secure file storage with private ACL
- **Celery Background Processing**: Async job execution with retry logic
- **SQLAlchemy Database**: Async database operations with proper relationships

## Current Workflows

### **1. Simple Text-to-Audio**
```
Text Input → Job Creation → TTS Processing → Audio Output → Secure Storage
```

### **2. Book Processing**
```
Book Input → Chapter Detection → Parallel Processing → Audio Generation → Result Aggregation
```

### **3. Multi-Chapter Processing**
```
Book Input → Chapter Analysis → Child Job Creation → Parallel Execution → Progress Tracking → Final Assembly
```

### **Output Structure**
```
digitalocean_spaces/
├── jobs/{job_id}/
│   ├── input.txt (original text)
│   ├── result.json (processing metadata)
│   └── output.mp3 (final audio)
└── chapters/{job_id}/
    ├── chapter_01.mp3
    ├── chapter_02.mp3
    └── playlist.m3u
```

## Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL database connection | Yes |
| `OPENAI_API_KEY` | OpenAI API key for TTS | Yes |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | No |
| `DO_SPACES_KEY` | DigitalOcean Spaces access key | Yes |
| `DO_SPACES_SECRET` | DigitalOcean Spaces secret | Yes |
| `DO_SPACES_ENDPOINT` | DigitalOcean Spaces endpoint | Yes |
| `DO_SPACES_BUCKET` | DigitalOcean Spaces bucket name | Yes |
| `JWT_SECRET_KEY` | JWT token signing key | Yes |
| `CELERY_BROKER_URL` | Redis URL for Celery | Yes |
| `TTS_PROVIDER` | Provider choice (`openai`/`eleven`) | No (default: `openai`) |
| `TTS_MAX_CONCURRENCY` | Parallel audio jobs | No (default: `8`) |

## Dependencies

### **Core Framework**
- **FastAPI + Uvicorn**: Async web framework with automatic OpenAPI documentation
- **Pydantic 2.0+**: Data validation and serialization
- **SQLAlchemy 2.0+**: Async database ORM with relationship management
- **Alembic**: Database migrations

### **Background Processing**
- **Celery**: Distributed task queue with Redis broker
- **AsyncIO**: Concurrent processing support

### **Audio & AI Services**
- **OpenAI 1.82+**: TTS services with voice synthesis
- **ElevenLabs 2.1+**: Alternative TTS provider
- **Pydub**: Audio processing (requires ffmpeg)

### **Infrastructure**
- **boto3**: AWS/DigitalOcean Spaces integration
- **PyJWT**: JWT token management
- **bcrypt**: Password hashing
- **pytest**: Testing framework with async support

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

### Recent Completed Work
- **CORE-49**: Playback progress tracking system with resume functionality
- **CORE-55**: Private ACL security for all DigitalOcean Spaces files
- **CORE-50**: Audio streaming API with resume support
- **CORE-54**: Legacy dependency cleanup and modernization
- **CORE-22-26**: Junjo workflow integration (completed but evolved to current unified system)

### Current Capabilities
- **Unified Job Management**: Single API for all processing types
- **Intelligent Book Processing**: Automatic chapter detection and parallel processing
- **Resume Functionality**: Chapter-level progress tracking
- **Secure File Storage**: Private ACL with pre-signed URLs
- **Background Processing**: Scalable Celery-based job execution

## Important Notes

### **System Requirements**
- **ffmpeg**: Required for audio processing and concatenation
- **PostgreSQL**: Database for job and user management
- **Redis**: Required for Celery task queue

### **Performance & Scaling**
- **Async Operations**: Full async/await support throughout the stack
- **Configurable Concurrency**: Adjustable parallelism for TTS processing
- **Background Processing**: Non-blocking job execution with Celery
- **Resume Support**: Efficient handling of long-form content

### **Security**
- **Private File Storage**: All uploads use private ACL with secure access
- **JWT Authentication**: Secure user session management
- **Input Validation**: Comprehensive request validation with Pydantic
- **Error Handling**: Graceful error handling with detailed logging

### **Cost Management**
- **TTS Usage Monitoring**: Track OpenAI/ElevenLabs API usage
- **Efficient Processing**: Smart text chunking to minimize API calls
- **Storage Optimization**: Secure file management with lifecycle policies

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
