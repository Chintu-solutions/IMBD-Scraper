#!/bin/bash
echo "🔧 Starting development environment..."

# Start infrastructure services
docker-compose up -d postgres redis minio

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check if backend dependencies are installed
if [ ! -d "backend/venv" ]; then
    echo "📦 Setting up backend virtual environment..."
    cd backend
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/venv" ]; then
    echo "📦 Setting up frontend virtual environment..."
    cd frontend
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

echo "✅ Development environment ready!"
echo ""
echo "🚀 To start development:"
echo "  Backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  Frontend: cd frontend && source venv/bin/activate && streamlit run src/app.py"
echo ""
echo "📊 Services:"
echo "  Database: localhost:5432"
echo "  Redis:    localhost:6379"
echo "  MinIO:    localhost:9000 (console: localhost:9001)"
