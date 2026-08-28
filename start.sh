#!/usr/bin/env bash
# businessintelligence.ai - Local Stack Runner (Bash)
set -e

echo "=================================================="
echo "  businessintelligence.ai - Stack Startup Script  "
echo "=================================================="

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Notice: .env not found. Copying from .env.example..."
        cp .env.example .env
    fi
fi

echo ""
echo "[1/2] Launching Backend API on http://localhost:8000..."
(cd backend && python -m uvicorn api.main:app --reload --port 8000) &
BACKEND_PID=$!

echo "[2/2] Launching Frontend on http://localhost:3000..."
(cd web && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Stack running!"
echo "  Backend API : http://localhost:8000"
echo "  Swagger Docs: http://localhost:8000/docs"
echo "  Web App     : http://localhost:3000"
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM
wait
