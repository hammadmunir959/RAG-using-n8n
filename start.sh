#!/bin/bash

# Document Intelligence WebApp - Quick Start Script

echo "🚀 Starting Document Intelligence WebApp..."
echo ""

# Check if n8n is running
if ! docker ps | grep -q n8n; then
    echo "📦 Starting n8n with Docker..."
    docker compose up -d
    echo "⏳ Waiting for n8n to be ready..."
    sleep 5
else
    echo "✅ n8n is already running"
fi

# Start backend
echo ""
echo "🔧 Starting FastAPI backend..."
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo "✅ Backend dependencies installed"
echo "🌐 Starting backend server on http://localhost:8001"
PORT=8001 python main.py &
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
sleep 3

# Start frontend
echo ""
echo "🎨 Starting React frontend..."
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

echo "✅ Frontend dependencies installed"
echo "🌐 Starting frontend server on http://localhost:3000"
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✨ All services started!"
echo ""
echo "📍 Access your application at: http://localhost:3000"
echo "📍 Backend API: http://localhost:8001"
echo "📍 n8n: http://localhost:5678"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for user interrupt
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait

