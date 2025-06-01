# StorytimeTTS API Architecture & Organization

## Overview

This document outlines the proposed API structure for StorytimeTTS to support multiple processing modes: single-voice narration (papers, non-fiction), multi-voice narration (fiction), and full book processing with intelligent chapter splitting.

## Current State Analysis

### Existing API Structure
```
/api/v1/tts/generate           # Simple TTS generation (Celery-based)
/api/v1/chapters/parse         # Chapter parsing (Junjo-based)
/api/v1/chapters/parse-file    # File-based chapter parsing
/health                        # Health check
```

### Current Limitations
- `/tts/generate` bypasses sophisticated Junjo workflows
- No unified job management system
- Limited to single processing mode
- No book-level management
- Character parsing and audio generation are disconnected

## Proposed API Structure

### 1. Book Management (`/api/v1/books`)
Handles full book uploads, metadata, and chapter management.

```
POST   /api/v1/books                    # Upload full book
GET    /api/v1/books/{book_id}          # Get book metadata  
DELETE /api/v1/books/{book_id}          # Delete book
POST   /api/v1/books/{book_id}/split    # Split book into chapters
GET    /api/v1/books/{book_id}/chapters # List chapters
```

### 2. Chapter Management (`/api/v1/chapters`) 
Manages individual chapters and parsing operations.

```
POST   /api/v1/chapters                 # Upload/create single chapter
GET    /api/v1/chapters/{chapter_id}    # Get chapter content
POST   /api/v1/chapters/{chapter_id}/parse # Parse chapter (narrative analysis)
GET    /api/v1/chapters/{chapter_id}/segments # Get parsed segments
```

### 3. Audio Generation Jobs (`/api/v1/jobs`)
Unified job processing system for all audio generation modes.

```
POST   /api/v1/jobs                     # Create audio generation job
GET    /api/v1/jobs/{job_id}           # Get job status
GET    /api/v1/jobs/{job_id}/audio     # Download audio file
DELETE /api/v1/jobs/{job_id}           # Cancel job
```

## Processing Modes

### Single-Voice Mode
For papers, documentation, non-fiction content.

**Request Example:**
```json
{
  "type": "single_voice",
  "source": {
    "book_id": "uuid" | "chapter_id": "uuid" | "text": "..."
  },
  "voice_config": {
    "provider": "openai",
    "voice": "alloy",
    "speed": 1.0
  }
}
```

**Workflow:** Direct TTSGenerator call (no Junjo overhead)

### Multi-Voice Mode
For narrative fiction with character dialogue.

**Request Example:**
```json
{
  "type": "multi_voice", 
  "source": {
    "book_id": "uuid" | "chapter_id": "uuid"
  },
  "voice_config": {
    "provider": "openai",
    "narrator_voice": "alloy",
    "auto_assign_characters": true
  },
  "requires_parsing": true
}
```

**Workflow:** Chapter parsing → Character analysis → Multi-voice audio generation (Junjo-based)

### Book Processing Mode
For full books requiring chapter splitting and batch processing.

**Request Example:**
```json
{
  "type": "book_processing",
  "source": {
    "book_id": "uuid"
  },
  "processing_config": {
    "split_chapters": true,
    "mode": "multi_voice" | "single_voice",
    "voice_config": {...}
  }
}
```

**Workflow:** Book splitting → Chapter processing → Audio generation (Junjo-based)

## Junjo Integration Strategy

### Where Junjo is Used
1. **Chapter Parsing Jobs** → Use existing `workflows/chapter_parsing.py`
2. **Multi-Voice Audio Jobs** → Use existing `workflows/audio_generation.py`  
3. **Book Splitting Jobs** → New Junjo workflow for intelligent chapter detection
4. **Single-Voice Jobs** → Simple TTSGenerator (no Junjo needed)

### Job Processing Engine
```python
async def process_job(job: Job):
    if job.type == JobType.SINGLE_VOICE:
        # Direct TTSGenerator call (no Junjo)
        await simple_tts_task(job)
        
    elif job.type == JobType.MULTI_VOICE:
        # Use chapter_parsing + audio_generation workflows
        parsed_chapter = await run_chapter_parsing_workflow(job.source_content)
        await run_audio_generation_workflow(parsed_chapter, job.voice_config)
        
    elif job.type == JobType.BOOK_PROCESSING:
        # New book splitting workflow + recursive job creation
        chapters = await run_book_splitting_workflow(job.source_content)
        for chapter in chapters:
            create_child_job(chapter, job.voice_config)
            
    elif job.type == JobType.CHAPTER_PARSING:
        # Pure parsing workflow (no audio)
        await run_chapter_parsing_workflow(job.source_content)
```

## Database Schema Extensions

### New Models Required

```python
class Book(Base):
    id: str = Field(primary_key=True)
    title: str
    status: BookStatus
    text_key: str  # DigitalOcean Spaces key
    chapters: List[Chapter] = relationship("Chapter", back_populates="book")
    processing_jobs: List[Job] = relationship("Job", back_populates="book")

class Chapter(Base):
    id: str = Field(primary_key=True)
    book_id: str = ForeignKey("book.id")
    chapter_number: int
    title: str
    content_key: str  # Spaces storage key
    book: Book = relationship("Book", back_populates="chapters")

class Job(Base):
    id: str = Field(primary_key=True)
    type: JobType  # SINGLE_VOICE, MULTI_VOICE, BOOK_PROCESSING, CHAPTER_PARSING
    source_type: SourceType  # BOOK, CHAPTER, TEXT
    source_id: str
    status: JobStatus  # PENDING, RUNNING, COMPLETED, FAILED
    result_key: str  # Audio file in Spaces
    error_msg: str = None
    progress_pct: int = 0
    voice_config: dict = {}
    created_at: datetime
    updated_at: datetime

class JobType(Enum):
    SINGLE_VOICE = "single_voice"
    MULTI_VOICE = "multi_voice" 
    BOOK_PROCESSING = "book_processing"
    CHAPTER_PARSING = "chapter_parsing"

class SourceType(Enum):
    BOOK = "book"
    CHAPTER = "chapter"
    TEXT = "text"
```

## Resource Relationships

```
Book (1) → Chapters (N) → Audio Jobs (N)
                      ↘ Parse Jobs (N)
```

## Migration Strategy

### Phase 1: Extend Current System
1. Keep existing `/tts/generate` for backward compatibility
2. Add new database models (Job, Chapter extensions)
3. Create new `/jobs` API endpoints

### Phase 2: Implement New Workflows
1. Create book management API (`/books`)
2. Implement job processing engine with Junjo integration
3. Add book splitting workflow

### Phase 3: Consolidation
1. Migrate existing functionality to job-based system
2. Deprecate old endpoints
3. Optimize performance and add advanced features

## Example Usage Flows

### 1. Simple Paper Reading
```bash
POST /api/v1/jobs
{
  "type": "single_voice",
  "source": {"text": "Research paper content..."},
  "voice_config": {"provider": "openai", "voice": "alloy"}
}
```

### 2. Fiction Chapter with Multiple Voices
```bash
POST /api/v1/jobs  
{
  "type": "multi_voice",
  "source": {"text": "Chapter 1 content..."},
  "voice_config": {"provider": "openai", "auto_assign_characters": true}
}
```

### 3. Full Book Processing
```bash
# Upload book
POST /api/v1/books
# Split into chapters  
POST /api/v1/books/{book_id}/split
# Process with multi-voice
POST /api/v1/jobs
{
  "type": "book_processing", 
  "source": {"book_id": "uuid"},
  "processing_config": {"mode": "multi_voice"}
}
```

## Implementation Priorities

### High Priority
1. **Job management system** - Core infrastructure for unified processing
2. **Database migrations** - Add new models and relationships
3. **Book management API** - Content upload and organization

### Medium Priority  
1. **Book splitting workflow** - Intelligent chapter detection
2. **Multi-voice job processing** - Integration with existing Junjo workflows
3. **Migration of existing endpoints** - Backward compatibility

### Low Priority
1. **Advanced voice configuration** - Per-character voice assignment
2. **Batch processing optimization** - Performance improvements
3. **Audio post-processing** - Enhanced audio quality features

## Current Architecture Gaps

### What Currently Uses Junjo
- `/api/v1/chapters/parse` endpoints use `workflows/chapter_parsing.py`
- Audio generation workflow exists but isn't used by API (`workflows/audio_generation.py`)

### What Doesn't Use Junjo
- `/api/v1/tts/generate` uses simple Celery task with sequential `TTSGenerator`
- No orchestration for complex multi-step processes
- No observability or retry logic for failures

### Integration Points
- Celery tasks should call Junjo workflows instead of direct service calls
- Job processing engine should determine when to use Junjo vs simple processing
- OpenTelemetry tracing should be consistent across all processing modes