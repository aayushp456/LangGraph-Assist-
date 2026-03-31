#!/bin/bash

# Support Agent Backend Startup Script

echo "🚀 Starting Support Agent Backend..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from env.template..."
    cp env.template .env
    echo "✅ Created .env file. Please edit it with your API keys."
    echo ""
fi

# Initialize empty database if it doesn't exist (no seed data)
if [ ! -f backend/data/tickets.db ] || [ ! -s backend/data/tickets.db ]; then
    echo "No existing database found. Initializing empty database..."
    python -c "from backend.sqlite_db import init_db; init_db(); print('✅ Empty database initialized')"
    echo ""
fi

# Check if MongoDB is needed
USE_MONGODB=$(grep "USE_MONGODB" .env | cut -d '=' -f2)
if [ "$USE_MONGODB" = "true" ]; then
    echo "📊 Checking MongoDB connection..."
    # This will be checked when the app starts
fi

# Navigate to project root
cd "$(dirname "$0")"

echo "📦 Starting FastAPI server..."
echo "   URL: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""

# Start uvicorn from project root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
