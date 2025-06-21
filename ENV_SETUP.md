# Environment Configuration Guide

This guide explains how to properly configure StorytimeTTS for different environments: local development, Docker, and production.

## Environment Types

StorytimeTTS supports three environments:
- **`dev`**: Local development (default)
- **`docker`**: Docker Compose deployment
- **`production`**: Production deployment (via Kamal)

## Configuration Files

### Local Development (.env)
```bash
# Copy from .env.example
cp .env.example .env
# Edit .env with your local settings
```

Key settings for local development:
- `ENV=dev`
- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/storytime`
- `REDIS_URL=redis://localhost:6379/0`

### Docker Development (.env.docker)
```bash
# Already created with Docker-specific settings
# Edit .env.docker to add your API keys
```

Key settings for Docker:
- `ENV=docker`
- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/storytime`
- `REDIS_URL=redis://redis:6379/0`

### Production (.env.production)
```bash
# Copy from .env.production.example
cp .env.production.example .env.production
# Edit with production values
```

Key settings for production:
- `ENV=production`
- Database and Redis URLs pointing to production infrastructure
- All API keys and secrets properly configured

## Environment Detection

The application automatically detects and validates configuration based on the `ENV` variable:

1. **Automatic URL Resolution**: If DATABASE_URL or REDIS_URL are not set, the system provides sensible defaults for `dev` and `docker` environments
2. **Production Validation**: Production requires explicit configuration of all critical settings
3. **Startup Logging**: Clear environment information is logged on startup

## Running in Different Environments

### Local Development
```bash
# Start local PostgreSQL and Redis
# Then run:
uvicorn src.storytime.api.main:app --reload
```

### Docker Development
```bash
# Uses .env.docker automatically
docker-compose up --build
```

### Production Deployment
```bash
# Kamal reads from config/deploy.yml
kamal deploy
```

## Troubleshooting

### Common Issues

1. **"Name or service not known" error**
   - Check that service names in DATABASE_URL match your docker-compose.yml
   - Ensure you're using the correct environment file

2. **Missing environment variables**
   - Check startup logs for warnings
   - Verify all required variables are set for your environment

3. **Wrong database connection**
   - Check the ENV variable is set correctly
   - Verify DATABASE_URL matches your environment

### Verification

On startup, you should see logs like:
```
============================================================
Starting StorytimeTTS in DOCKER environment
============================================================
Environment: docker
Database URL: postgresql+asyncpg://postgres:postgres@db:5432/storytime
Redis URL: redis://redis:6379/0
DO Spaces Bucket: storytime-local
TTS Provider: openai
============================================================
```

## Security Notes

- Never commit `.env`, `.env.docker`, or `.env.production` files
- Use strong, unique JWT_SECRET_KEY values for each environment
- Keep production credentials separate and secure
- Use environment-specific DO Spaces buckets to avoid data mixing
