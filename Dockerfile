# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install OS dependencies including Node.js
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libpq-dev \
    gcc \
    curl \
    postgresql-client \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy dependency definitions
COPY pyproject.toml /app/

# Install uv and use it to install all dependencies from pyproject.toml
RUN pip install uv && uv pip install --system --requirements pyproject.toml

# Install playwright browsers for web scraping
RUN playwright install --with-deps chromium

# Build React client
COPY client /app/client
WORKDIR /app/client
ARG CACHEBUST=1
ARG VITE_API_BASE_URL=https://plinytheai.com
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm cache clean --force && \
    rm -rf node_modules package-lock.json && \
    npm install @rollup/rollup-linux-x64-gnu && \
    npm install && \
    npm run build

# Copy application code and built client
WORKDIR /app
COPY src /app/src
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
RUN mkdir -p /app/static && cp -r /app/client/dist/* /app/static/

# Expose API port
EXPOSE 8000

# Set Python path so 'src' is importable
ENV PYTHONPATH=/app/src

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/up || exit 1

# Run the application
CMD ["uvicorn", "storytime.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
