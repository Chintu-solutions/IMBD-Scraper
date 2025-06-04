#!/bin/bash
echo "🚀 Deploying Enhanced IMDb Scraper..."

# Build and start all services
docker-compose up --build -d

# Run migrations
docker-compose exec backend alembic upgrade head

echo "✅ Deployment complete!"
