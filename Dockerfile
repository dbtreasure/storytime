# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install OS dependencies
RUN apt-get update && apt-get install -y build-essential ffmpeg && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy dependency definitions
COPY pyproject.toml /app/

# Install uv and use it to install all dependencies from pyproject.toml
RUN pip install uv && uv pip install --system --requirements pyproject.toml

# Copy application code
COPY src /app/src

# Expose API port
EXPOSE 8000

# Set Python path so 'src' is importable
ENV PYTHONPATH=/app/src

# Run the application
CMD ["uvicorn", "src.storytime.api.main:app", "--host", "0.0.0.0", "--port", "8000"] 