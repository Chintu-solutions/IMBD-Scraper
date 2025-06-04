#!/bin/bash
echo "🚀 Setting up Enhanced IMDb Scraper..."

# Copy environment file
cp .env.example .env

# Start services
docker-compose up -d postgres redis minio

# Wait for services
sleep 10

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Install frontend dependencies
cd ../frontend
pip install -r requirements.txt

echo "✅ Setup complete! Run 'docker-compose up' to start all services."
