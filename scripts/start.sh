#!/bin/bash
set -e

# Change to project root where alembic.ini is located
cd /app

# Extract database connection details from DATABASE_URL
# Format: postgresql+asyncpg://user:pass@host:port/dbname
if [[ -z "$DATABASE_URL" ]]; then
  echo "❌ DATABASE_URL is not set!"
  exit 1
fi

# Parse the DATABASE_URL to extract components
# Remove the scheme (postgresql+asyncpg://)
DB_CONN="${DATABASE_URL#*://}"
# Extract user:pass@host:port/dbname
DB_USER_PASS="${DB_CONN%%@*}"
DB_HOST_PORT_DB="${DB_CONN#*@}"
# Extract host:port
DB_HOST_PORT="${DB_HOST_PORT_DB%%/*}"
# Extract just the host
DB_HOST="${DB_HOST_PORT%%:*}"
# Extract the port (default to 5432 if not specified)
DB_PORT="${DB_HOST_PORT##*:}"
if [[ "$DB_PORT" == "$DB_HOST" ]]; then
  DB_PORT="5432"
fi
# Extract username
DB_USER="${DB_USER_PASS%%:*}"

echo "⏳ Waiting for database to be ready..."
echo "📍 Connecting to: ${DB_HOST}:${DB_PORT} as ${DB_USER}"

# Wait for database to be available
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  echo "🔄 Waiting for database at ${DB_HOST}:${DB_PORT}..."
  sleep 2
done
echo "✅ Database is ready!"

echo "🔄 Running database migrations..."
uv run alembic upgrade head

echo "🚀 Starting application..."
exec uvicorn src.storytime.api.main:app --host 0.0.0.0 --port 8000 ${@}