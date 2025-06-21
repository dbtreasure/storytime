# StorytimeTTS Deployment Scripts

Simple scripts to manage different environments for StorytimeTTS.

## Scripts

### `./scripts/docker` - Docker Development
Runs full stack with Docker Compose.

**Requirements:**
- Docker Desktop running
- `.env.docker` file configured

**Usage:**
```bash
./scripts/docker                 # Start services in background
./scripts/docker --logs          # Start and show logs
./scripts/docker --clean         # Clean rebuild
./scripts/docker --down          # Stop services
./scripts/docker --help          # Show help
```

**What it does:**
- Uses `.env.docker` for configuration
- Client dev server on port 3000
- API on port 8000
- PostgreSQL on port 5432
- Redis on port 6379

### `./scripts/production` - Production Deployment
Deploys to production using Kamal.

**Requirements:**
- Kamal installed (`gem install kamal`)
- `.kamal/secrets` file configured
- Docker running

**Usage:**
```bash
./scripts/production              # Deploy to production
./scripts/production --setup     # First-time setup
./scripts/production --build-only # Build and push only
./scripts/production --logs       # Deploy and show logs
./scripts/production --status     # Check status
./scripts/production --help       # Show help
```

**What it does:**
- Builds images with production API URL
- Pushes to registry
- Deploys with Kamal
- Zero-downtime deployment

## Environment Configuration

### Docker Development (.env.docker)
```env
ENV=docker
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/storytime
REDIS_URL=redis://redis:6379/0
OPENAI_API_KEY=your-key
JWT_SECRET_KEY=your-secret
```

### Production (.kamal/secrets)
```env
DATABASE_URL=postgresql+asyncpg://user:pass@prod-host:5432/storytime
REDIS_URL=redis://prod-host:6379/0
OPENAI_API_KEY=prod-key
JWT_SECRET_KEY=prod-secret
DO_SPACES_KEY=prod-key
DO_SPACES_SECRET=prod-secret
# ... other production secrets
```

## Quick Start

1. **Docker Development:**
   ```bash
   # Ensure .env.docker has your API keys
   ./scripts/docker
   # Access at http://localhost:3000
   ```

2. **Production Deployment:**
   ```bash
   # First time only:
   ./scripts/production --setup
   
   # Regular deployments:
   ./scripts/production
   ```