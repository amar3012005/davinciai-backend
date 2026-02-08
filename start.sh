#!/bin/bash

# DaVinci AI Backend - Quick Start Script

echo "🚀 Starting DaVinci AI Backend Prototype..."
echo ""

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please update with your API keys."
fi

# Start the server
echo "📡 Starting FastAPI server on http://localhost:8000"
echo "📄 API docs available at http://localhost:8000/api/docs"
echo ""

python -m uvicorn app.main:app --reload --port 8000
