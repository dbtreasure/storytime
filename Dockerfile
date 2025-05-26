# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install OS dependencies
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy dependency definitions
COPY pyproject.toml /app/

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic[email]

# Copy application code
COPY src /app/src

# Expose API port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "storytime.api.main:app", "--host", "0.0.0.0", "--port", "8000"] 