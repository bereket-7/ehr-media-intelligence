#!/bin/sh
set -e

# Automatically seed the database on first run if database file is missing
if [ ! -f "$SQLITE_DB_PATH" ]; then
    echo "================================================================="
    echo "First container launch: Seeding synthetic EHR demo data..."
    echo "================================================================="
    python /app/backend/scripts/seed_data.py
fi

echo "================================================================="
echo "Starting EHR Media Intelligence API on http://0.0.0.0:8000"
echo "================================================================="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
