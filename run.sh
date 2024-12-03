#!/bin/bash

# Kill any existing processes
echo "Stopping existing processes..."
pkill -f gunicorn
pkill -f "node.*react-scripts start"
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 2  # Give processes time to shut down

# Start the FastAPI backend
gunicorn src.api:app -c gunicorn_config.py &

# Start the React frontend
cd frontend && npm start &

# Wait for both processes
wait 