# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StorytimeTTS is an AI-powered audiobook generation platform that transforms text content into high-quality audiobooks. The system has evolved from complex multi-voice character processing to a streamlined, unified job management platform supporting both simple text-to-audio conversion and intelligent book processing with automatic chapter detection and parallel processing.

## Recent Updates

### **Environment-Based Feature Flags**
We've implemented a flexible feature flag system that adapts based on the environment:

- **API Endpoint**: `/api/v1/environment` returns current environment and feature flags
- **Client Utility**: `client/src/utils/environment.ts` provides environment detection
- **Registration Control**: User signup is automatically enabled in dev/docker, disabled in production
- **Extensible System**: Easy to add new feature flags for A/B testing or gradual rollouts

The environment is controlled by the `ENV` variable:
- `ENV=dev` - Local development (signup enabled)
- `ENV=docker` - Docker Compose (signup enabled)
- `ENV=production` - Production/Kamal deployment (signup disabled)

### **Simplified React Client Deployment**
The React client is now served as static assets directly from the FastAPI application:
- No separate client worker needed in Kamal
- Builds during Docker image creation
- Serves from `/app/static/` via FastAPI
- Removed unnecessary `client` accessory from `config/deploy.yml`

### **MCP Server Integration**
The system includes a complete MCP (Model Context Protocol) server for voice assistant integration:
- **SSE Endpoint**: `/mcp-server/sse` for real-time communication
- **HTTP Endpoint**: `/mcp-server/messages` for direct API calls
- **Authentication**: JWT Bearer token required
- **Available Tools**: `search_library`, `search_job`, `ask_job_question`
- **OpenAI Realtime API**: Complete integration in `src/storytime/voice_assistant/`

## Development Commands

### Quick Start
```bash
# Docker development
./scripts/docker

# Production deployment
./scripts/production
```

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

### Code Quality Hooks
The project uses Claude Code hooks (`.claude.json`) to enforce code quality:

```bash
# Hooks automatically run:
# - Python: ruff check --fix && ruff format (after Python edits)
# - Client: npm run lint && npm run typecheck (after TS/React edits)
# - Build: npm run build (after client changes complete)

# Manual validation commands:
uvx ruff check . --fix        # Fix Python linting issues
uvx ruff format .             # Format Python code
cd client && npm run lint     # Lint client code
cd client && npm run typecheck # Check TypeScript types
cd client && npm run build    # Test client build
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

### Client Build (for Static File Serving)
```bash
# Build React client for production
cd client && npm run build

# Copy built assets to static directory (for FastAPI static serving)
cp -r client/dist/* static/

# Note: static/ directory is in .gitignore - build assets are generated during deployment
```

### Docker
```bash
# Build and run with docker-compose (uses .env.docker automatically)
docker-compose up --build

# Run individual container
docker build -t storytime .
docker run -p 8000:8000 storytime
```

### Environment Management Scripts
Simple scripts handle all environment complexity:

- **`./scripts/docker`**: Docker Compose development
- **`./scripts/production`**: Production deployment with Kamal

Environment files:
- `.env.docker`: Docker Compose
- `.kamal/secrets`: Production secrets

See `scripts/README.md` for detailed usage guide.

### MCP Inspector Testing
Use the MCP Inspector to test the MCP server endpoints:

```bash
# Start MCP Inspector (generates new session token each time)
npx @modelcontextprotocol/inspector

# This will output:
# 🔑 Session token: [NEW_TOKEN_HERE]
# 🔗 Open inspector with token pre-filled:
#    http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=[NEW_TOKEN_HERE]
```

**Important Setup Steps:**
1. **Use the generated URL** - The session token changes each run
2. **Transport Type**: Select "SSE" (not Streamable HTTP)
3. **URL**: Set to `http://localhost:8000/mcp-server/sse`
4. **Authentication**: Use Bearer token from user login (JWT format)
5. **Configuration**: The proxy session token is auto-filled from URL

**Available Tools for Testing:**
- `search_library` - Search across user's entire audiobook library
- `search_job` - Search within specific audiobook by job ID
- `ask_job_question` - Ask questions about specific audiobook content

**Authentication Requirements:**
- MCP server uses JWT Bearer tokens for user authentication
- Inspector proxy uses separate session tokens for inspector access
- Both are required for successful testing

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

| Variable | Description | Required | Default (dev/docker) |
|----------|-------------|----------|---------------------|
| `ENV` | Environment (`dev`/`docker`/`production`) | Yes | `dev` |
| `DATABASE_URL` | PostgreSQL database connection | Yes* | Auto-set for dev/docker |
| `REDIS_URL` | Redis connection URL | Yes* | Auto-set for dev/docker |
| `OPENAI_API_KEY` | OpenAI API key for TTS | Yes | - |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | No | - |
| `DO_SPACES_KEY` | DigitalOcean Spaces access key | Yes | - |
| `DO_SPACES_SECRET` | DigitalOcean Spaces secret | Yes | - |
| `DO_SPACES_ENDPOINT` | DigitalOcean Spaces endpoint | Yes | - |
| `DO_SPACES_BUCKET` | DigitalOcean Spaces bucket name | Yes | - |
| `JWT_SECRET_KEY` | JWT token signing key | Yes | - |
| `CELERY_BROKER_URL` | Redis URL for Celery | Yes* | Same as REDIS_URL |
| `TTS_PROVIDER` | Provider choice (`openai`/`eleven`) | No | `openai` |

*Required for production, auto-configured for dev/docker environments

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
- **Environment Features**: Implemented environment-based feature flags with conditional signup
- **Client Deployment**: Simplified React app serving as static assets (removed separate worker)

### Current Capabilities
- **Unified Job Management**: Single API for all processing types
- **Intelligent Book Processing**: Automatic chapter detection and parallel processing
- **Resume Functionality**: Chapter-level progress tracking
- **Secure File Storage**: Private ACL with pre-signed URLs
- **Background Processing**: Scalable Celery-based job execution
- **Feature Flags**: Environment-aware feature toggles (signup, debug mode, etc.)
- **Simplified Deployment**: React client served as static assets from FastAPI

## MCP (Model Context Protocol) Voice Assistant Architecture

### **CRITICAL: Multi-Layer Tool Registration System**

The voice assistant uses a **complex multi-layer MCP tool system** that requires **ALL LAYERS** to be kept in sync when adding new tools. Failure to update any layer will result in tools not being available to the LLM.

### **Tool Registration Architecture (5 Required Updates for New Tools):**

#### **1. MCP Tool Implementation (`src/storytime/mcp/tools/`)**
- Individual tool files (e.g., `tutor_chat.py`, `xray_lookup.py`)
- Each tool must be implemented as async function with proper error handling
- Tools must validate user authentication and database access

#### **2. MCP Tools Export (`src/storytime/mcp/tools/__init__.py`)**
```python
# ALL tools must be exported here
from .tutor_chat import tutor_chat
from .xray_lookup import xray_lookup
__all__ = ["ask_about_book", "search_audiobook", "search_library", "tutor_chat", "xray_lookup"]
```

#### **3. HTTP MCP Server Registration (`src/storytime/mcp/http_server.py`)**
```python
# Tool imports at top
from storytime.mcp.tools.tutor_chat import tutor_chat
from storytime.mcp.tools.xray_lookup import xray_lookup

# Tool schema definition in tools/list endpoint (lines ~190-231)
{
    "name": "tutor_chat",
    "description": "Engage in Socratic tutoring dialogue...",
    "inputSchema": { /* parameters */ }
}

# Tool handler in tools/call endpoint (lines ~246-249)
elif tool_name == "tutor_chat":
    result = await handle_tutor_chat_tool(arguments, request)

# Tool handler function implementation (lines ~660+)
async def handle_tutor_chat_tool(arguments, request):
    # Implementation
```

#### **4. OpenAI Realtime API Tools (`src/storytime/voice_assistant/pipecat_assistant.py`)**
**CRITICAL**: There's a **hardcoded tools list** (lines ~142-238) that gets passed directly to OpenAI Realtime API. This MUST include all tools:
```python
# Define tools for OpenAI Realtime session
tools = [
    {"type": "function", "name": "search_library", ...},
    {"type": "function", "name": "search_job", ...}, 
    {"type": "function", "name": "ask_job_question", ...},
    {"type": "function", "name": "tutor_chat", ...},      # MUST ADD NEW TOOLS HERE
    {"type": "function", "name": "xray_lookup", ...},     # MUST ADD NEW TOOLS HERE
]
```

#### **5. System Instructions (`src/storytime/voice_assistant/pipecat_assistant.py`)**
The `_default_instructions()` method builds tool descriptions dynamically, but the base tool list must be updated:
```python
tool_descriptions = {
    "search_library": "Search across the user's entire audiobook library",
    "search_job": "Search within specific audiobook content by job ID",
    "ask_job_question": "Ask questions about specific audiobook content", 
    "tutor_chat": "Engage in Socratic tutoring dialogue about audiobook content",    # ADD HERE
    "xray_lookup": "Provide contextual content lookup (characters, concepts, etc.)" # ADD HERE
}
```

### **MCP Server Architecture**

#### **Active MCP Server: `http_server.py`**
- **Used by**: Voice assistant via Pipecat MCP integration
- **Endpoint**: `/mcp-server/sse` (SSE) and `/mcp-server/messages` (HTTP)
- **Authentication**: JWT Bearer tokens required
- **Purpose**: Primary MCP server for voice assistant integration

#### **Unused MCP Servers (Keep for Reference)**
- **`server.py`**: FastMCP-based server (standalone, not integrated)
- **`fastapi_integration.py`**: Alternative FastMCP integration (incomplete, only 2 tools)

### **Available MCP Tools**

1. **`search_library`**: Search across user's entire audiobook library
2. **`search_job`**: Search within specific audiobook by job ID  
3. **`ask_job_question`**: Ask questions about specific audiobook content
4. **`tutor_chat`**: Engage in Socratic tutoring dialogue about content ⭐
5. **`xray_lookup`**: Contextual content lookup (Kindle X-ray style) ⭐

### **Voice Assistant Integration Flow**

1. **MCP Server Start**: `http_server.py` registers all 5 tools via SSE endpoint
2. **Pipecat Connection**: Voice assistant connects to `/mcp-server/sse` 
3. **Tool Registration**: Pipecat MCP service registers tools with LLM
4. **OpenAI Realtime**: Hardcoded tools list passed to OpenAI Realtime API
5. **User Interaction**: LLM can call tools, which route through MCP server to tool handlers

### **Testing MCP Tools**

#### **Direct API Testing**
```bash
# Test tools/list endpoint
curl -H "Authorization: Bearer $JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":"test"}' \
     http://localhost:8000/mcp-server/messages

# Should return all 5 tools: search_library, search_job, ask_job_question, tutor_chat, xray_lookup
```

#### **MCP Inspector Testing**  
```bash
# Start MCP Inspector
npx @modelcontextprotocol/inspector

# Configuration:
# - Transport: SSE 
# - URL: http://localhost:8000/mcp-server/sse
# - Auth: Bearer <JWT_TOKEN>
```

### **Common Issues and Solutions**

#### **"Voice assistant only sees 3 tools"**
- **Cause**: Hardcoded tools list in `pipecat_assistant.py` not updated
- **Fix**: Add new tools to lines ~142-238 in `pipecat_assistant.py`

#### **"MCP server returns tool not found"**
- **Cause**: Tool not registered in `http_server.py` handler
- **Fix**: Add tool name check and handler function in `http_server.py`

#### **"Tool handler not found"**
- **Cause**: Handler function not implemented
- **Fix**: Implement `handle_<tool_name>_tool()` function in `http_server.py`

### **Adding New MCP Tools Checklist**

- [ ] 1. Create tool implementation in `src/storytime/mcp/tools/new_tool.py`
- [ ] 2. Export tool in `src/storytime/mcp/tools/__init__.py` 
- [ ] 3. Add tool schema to `http_server.py` tools/list endpoint
- [ ] 4. Add tool handler case to `http_server.py` tools/call endpoint
- [ ] 5. Implement handler function in `http_server.py`
- [ ] 6. **CRITICAL**: Add tool to hardcoded tools list in `pipecat_assistant.py`
- [ ] 7. Update tool descriptions in `pipecat_assistant.py` instructions
- [ ] 8. Test with MCP Inspector and voice assistant
- [ ] 9. Restart Docker to apply changes

**NEVER skip step 6** - the hardcoded tools list is what OpenAI Realtime API actually sees!

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

When working with API endpoints in this codebase:

  **TYPE SAFETY APPROACH: Pydantic → Zod → TypeScript**

  We use Zod schemas for runtime validation and TypeScript type inference instead of OpenAPI generators,
  which have proven unreliable with complex schema references.

  1. ALWAYS define proper Pydantic response models in the FastAPI backend (src/storytime/models.py)
  2. ALWAYS use response_model=MyResponseModel in FastAPI route decorators
  3. ALWAYS maintain corresponding Zod schemas in client/src/schemas/index.ts
  4. ALWAYS use Zod schemas for runtime validation in API client methods
  5. ALWAYS import types from client/src/schemas/ (not generated/)

  WORKFLOW:
  - Backend: Add Pydantic model → Use in route decorator → Restart API
  - Frontend: Add corresponding Zod schema → Use .parse() in API client → Import inferred types
  - Runtime safety: Zod validates API responses and catches schema mismatches early

  This approach provides both compile-time type safety AND runtime validation while avoiding
  OpenAPI generator bugs with complex schema references (anyOf + $ref combinations).
