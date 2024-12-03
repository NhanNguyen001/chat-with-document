#!/bin/bash
# Start the FastAPI backend in development mode
uvicorn src.api:app --reload --port 8000 &

# Start the React frontend
cd frontend && npm start &

# Wait for both processes
wait 