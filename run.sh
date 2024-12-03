#!/bin/bash
# Start the FastAPI backend
gunicorn src.api:app -c gunicorn_config.py &

# Start the React frontend
cd frontend && npm start &

# Wait for both processes
wait 