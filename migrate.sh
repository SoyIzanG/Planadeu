#!/bin/bash

# Production Database Migration Script
echo "Running database migrations for production..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set!"
    echo "Please set DATABASE_URL in Render dashboard or environment"
    exit 1
fi

echo "Using database: $DATABASE_URL"

# Run migrations
python -c "
from app import create_app
from flask_migrate import upgrade
import os

app = create_app('production')
with app.app_context():
    print('Running database migrations...')
    try:
        upgrade()
        print('Migrations completed successfully!')
    except Exception as e:
        print(f'Migration error: {e}')
        exit(1)
"

echo "Migration process completed."
