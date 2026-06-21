#!/bin/bash
# Convenience script to run the backend

set -e

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your settings before running."
    exit 1
fi

# Run the application
echo "Starting ElBot Backend..."
echo "API Documentation: http://localhost:8500/docs"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8500