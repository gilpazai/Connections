#!/bin/bash
# Start VC Connections (FastAPI backend + Next.js frontend)
# Usage: ./start.sh

cd "$(dirname "$0")"

echo "Starting FastAPI backend on http://localhost:8000 ..."
PYTHONPATH=. .venv/bin/python -m uvicorn backend.api.main:app --port 8000 --reload &
BACKEND_PID=$!

echo "Starting Next.js frontend on http://localhost:3000 ..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "Both servers running."
echo "  App:     http://localhost:3000/login"
echo "  API:     http://localhost:8000/docs"
echo "  Login:   password is 'admin' (set ADMIN_PASSWORD in frontend/.env.local to change)"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" INT TERM
wait
