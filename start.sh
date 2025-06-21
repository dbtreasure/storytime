#!/bin/bash
set -e

# Change to project root where alembic.ini is located
cd /app

echo "⏳ Waiting for database to be ready..."
# Wait for database to be available
until pg_isready -h db -p 5432 -U postgres; do
  echo "🔄 Waiting for database..."
  sleep 2
done
echo "✅ Database is ready!"

echo "🔄 Running database migrations..."
uv run alembic upgrade head

echo "🚀 Starting application..."
exec uvicorn src.storytime.api.main:app --host 0.0.0.0 --port 8000 ${@}