# 📚 StorytimeTTS - AI-Powered Audiobook Generation Platform

Transform text content into high-quality audiobooks with intelligent processing! StorytimeTTS has evolved into a streamlined, unified job management platform supporting both simple text-to-audio conversion and intelligent book processing with automatic chapter detection.

## 🌟 Current Features

- **🎯 Unified Job Management**: Single API for all audiobook processing types
- **📖 Intelligent Book Processing**: Automatic chapter detection and structure analysis
- **🔄 Resume Functionality**: Chapter-level progress tracking for long-form content
- **🎙️ Multi-Provider TTS**: OpenAI and ElevenLabs voice synthesis
- **🔒 Secure Storage**: Private file storage with DigitalOcean Spaces
- **⚡ Background Processing**: Scalable Celery-based job execution
- **📊 Progress Tracking**: Real-time job status and step-by-step monitoring

## 🏗️ System Architecture

### **REST API Endpoints**
```
/api/v1/jobs/          - Complete job lifecycle management
/api/v1/audio/         - Audio streaming with resume support
/api/v1/progress/      - Playback progress and resume functionality
/api/v1/auth/          - JWT-based authentication
```

### **Processing Workflows**
```
Simple Text → Job Creation → TTS Processing → Audio Output → Secure Storage

Book Processing → Chapter Detection → Parallel Processing → Audio Generation → Result Aggregation

```

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone repository
git clone <repository-url>
cd storytime

# Install dependencies (preferred method)
uv sync

# Alternative installation
pip install -e .
```

### 2. Required Services

- **PostgreSQL**: Database for job and user management
- **Redis**: Task queue for background processing
- **DigitalOcean Spaces**: File storage (or AWS S3 compatible)

### 3. Environment Variables

```bash
# Database
export DATABASE_URL="postgresql://user:pass@localhost/storytime"

# AI Services
export OPENAI_API_KEY="your_openai_api_key"
export ELEVENLABS_API_KEY="your_elevenlabs_api_key"  # Optional

# File Storage
export DO_SPACES_KEY="your_spaces_access_key"
export DO_SPACES_SECRET="your_spaces_secret_key"
export DO_SPACES_ENDPOINT="your_spaces_endpoint"
export DO_SPACES_BUCKET="your_bucket_name"

# Authentication
export JWT_SECRET_KEY="your_jwt_secret_key"

# Background Processing
export CELERY_BROKER_URL="redis://localhost:6379/0"

# Optional Configuration
export TTS_PROVIDER="openai"  # or "eleven"
```

When using `docker-compose`, the tool will automatically load variables from a
`.env` file if one exists. Any environment variables set in your shell take
precedence over values from that file.

### 4. Start the Application

```bash
# Start the FastAPI server
cd src && python -m storytime.api.main

# Or with uvicorn directly
uvicorn storytime.api.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (separate terminal)
celery -A storytime.worker.celery_app worker --loglevel=info

# Build and start React client (separate terminal)
cd client && npm install && npm run dev
```

### 5. Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src/storytime

# Code quality checks
ruff check .
ruff format .
```

## 📋 Core Components

### **🎯 Unified Job System**
- **Job Types**: TEXT_TO_AUDIO, BOOK_PROCESSING
- **Step Tracking**: Granular progress monitoring with detailed error handling
- **Resume Support**: Chapter-level progress for long-form content

### **📖 Book Intelligence**
- **Chapter Detection**: Multiple strategies (numbered, roman numerals, content-based)
- **Content Analysis**: Automatic structure recognition for various book formats
- **Parallel Processing**: Concurrent chapter processing for faster results

### **🎙️ TTS Processing**
- **Smart Chunking**: Respects API limits with sentence/word boundary splitting
- **Voice Selection**: Configurable voice assignment per provider
- **Audio Concatenation**: Seamless stitching of audio segments

### **🔒 Secure Infrastructure**
- **Private Storage**: All files stored with private ACL for security
- **JWT Authentication**: Secure user session management
- **Pre-signed URLs**: Temporary access for downloads and streaming

## 🎭 Supported Job Types

### **1. Simple Text-to-Audio**
```python
{
    "job_type": "TEXT_TO_AUDIO",
    "text": "Your text content here...",
    "voice_config": {
        "provider": "openai",
        "voice": "nova"
    }
}
```

### **2. Book Processing**
```python
{
    "job_type": "BOOK_PROCESSING",
    "text": "Full book content...",
    "processing_config": {
        "max_concurrency": 4
    }
}
```


## 📊 API Usage Examples

### **Create a Job**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -d '{
       "job_type": "TEXT_TO_AUDIO",
       "text": "Hello, this is a test of the text-to-speech system.",
       "voice_config": {
         "provider": "openai",
         "voice": "nova"
       }
     }'
```

### **Check Job Status**
```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### **Stream Audio**
```bash
curl "http://localhost:8000/api/v1/audio/{job_id}/stream" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### **Update Progress**
```bash
curl -X PUT "http://localhost:8000/api/v1/progress/{job_id}" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -d '{
       "position": 120.5,
       "chapter": 1
     }'
```

## 📁 Output Structure

```
digitalocean_spaces/
├── jobs/{job_id}/
│   ├── input.txt              (Original text)
│   ├── result.json            (Processing metadata)
│   └── output.mp3             (Final audio)
├── chapters/{job_id}/
│   ├── chapter_01.mp3         (Individual chapters)
│   ├── chapter_02.mp3
│   └── playlist.m3u           (M3U playlist)
└── temp/
    └── processing_files/      (Temporary processing files)
```

## 🔧 Development

### **Database Migrations**
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### **Docker Development**
```bash
# Build and run with docker-compose
docker-compose up --build

# Run individual container
docker build -t storytime .
docker run -p 8000:8000 storytime
```

### **Code Quality**
```bash
# Lint and format
ruff check .
ruff format .

# Type checking
mypy src/
```

## 💰 Cost Estimates

### **OpenAI TTS**
- **Rate**: $0.015 per 1,000 characters
- **Average chapter**: ~$0.50-2.00
- **Full novel**: ~$50-200

### **ElevenLabs TTS**
- **Rate**: Varies by plan and usage
- **Character limits**: Plan-dependent
- **Voice cloning**: Premium feature

### **Infrastructure**
- **DigitalOcean Spaces**: $5/month + transfer costs
- **Database**: $15-50/month depending on size
- **Redis**: $15-25/month for managed service

## 🐛 Troubleshooting

### **Common Issues**

1. **Database Connection Errors**
   ```bash
   # Check database connection
   psql $DATABASE_URL

   # Run migrations
   alembic upgrade head
   ```

2. **Celery Worker Issues**
   ```bash
   # Check Redis connection
   redis-cli ping

   # Restart worker
   celery -A storytime.worker.celery_app worker --loglevel=debug
   ```

3. **File Storage Issues**
   ```bash
   # Test DigitalOcean Spaces connection
   python - <<'PY'
   import asyncio
   from storytime.infrastructure.spaces import SpacesClient

   async def main():
       client = SpacesClient()
       url = await client.get_presigned_download_url('test-key')
       print('Connected')

   asyncio.run(main())
   PY
   ```

4. **TTS Provider Errors**
   - Verify API keys are valid
   - Check rate limits and quotas
   - Monitor character usage

## 📊 Monitoring & Observability

### **Job Tracking**
- Real-time job status updates
- Step-by-step progress monitoring
- Detailed error reporting and logging

### **Performance Metrics**
- Processing time per job type
- TTS provider usage statistics
- Database query performance

### **Error Handling**
- Automatic retry logic with exponential backoff
- Graceful degradation for provider outages
- Comprehensive error logging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite (`pytest tests/`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- **OpenAI** for high-quality text-to-speech services
- **ElevenLabs** for advanced voice synthesis capabilities
- **FastAPI** for the excellent async web framework
- **Pydantic** for type-safe data validation
- **SQLAlchemy** for robust database operations
- **Celery** for reliable background job processing

---

**Ready to transform text into engaging audiobooks? Start with the API at `http://localhost:8000/docs`!** 🎧📚

## 🚧 Recent Updates

- ✅ **CORE-49**: Implemented playback progress tracking with resume functionality
- ✅ **CORE-55**: Enhanced security with private ACL for all file uploads
- ✅ **CORE-50**: Added audio streaming API with resume support
- ✅ **CORE-54**: Completed legacy dependency cleanup and modernization
- ✅ **Unified Job System**: Streamlined all processing through single job management API
- ✅ **Book Intelligence**: Added automatic chapter detection and parallel processing
- ✅ **Background Processing**: Implemented scalable Celery-based job execution
- ✅ **Environment-Based Features**: Added feature flags system with conditional user registration

For detailed development guidance, see [CLAUDE.md](CLAUDE.md)

## 🔐 Environment-Based Features

StorytimeTTS now includes environment-aware feature flags:

### **Feature Flag System**
- **Endpoint**: `/api/v1/environment` returns current environment and feature flags
- **User Registration**: Automatically enabled in `dev` and `docker` environments, disabled in `production`
- **Extensible**: Easy to add new feature flags for A/B testing or gradual rollouts

### **Environment Detection**
```javascript
// Client-side usage
import { getEnvironment } from './utils/environment';

const env = await getEnvironment();
if (env.features.signup_enabled) {
  // Show registration UI
}
```

### **Current Feature Flags**
- `signup_enabled`: Controls new user registration (true for dev/docker, false for production)
- `debug_mode`: Enables debug features (true for dev only)
- `demo_mode`: Reserved for future demo functionality

### **Configuration**
Set the environment via the `ENV` variable:
- `ENV=dev` - Local development (signup enabled)
- `ENV=docker` - Docker Compose (signup enabled)
- `ENV=production` - Production deployment (signup disabled)
