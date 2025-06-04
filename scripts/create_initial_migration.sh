#!/bin/bash
cd backend
echo "Creating initial database migration..."
alembic revision --autogenerate -m "Initial migration"
echo "Migration created! Run 'alembic upgrade head' to apply."
