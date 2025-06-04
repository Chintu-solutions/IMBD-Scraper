#!/bin/bash
echo "🧹 Cleaning up Enhanced IMDb Scraper..."

# Stop and remove containers
docker-compose down -v

# Remove downloaded data (optional)
read -p "Delete downloaded media files? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf data/downloads/*
    rm -rf data/exports/*
    echo "🗑️ Media files deleted"
fi

# Remove virtual environments (optional)
read -p "Delete virtual environments? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf backend/venv
    rm -rf frontend/venv
    echo "🗑️ Virtual environments deleted"
fi

echo "✅ Cleanup complete!"
