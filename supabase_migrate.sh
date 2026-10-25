#!/bin/bash

# Supabase Migration Script
echo "=== Supabase Database Migration ==="
echo ""

# Check if DATABASE_URL is provided
if [ -z "$1" ]; then
    echo "Usage: ./supabase_migrate.sh <DATABASE_URL>"
    echo ""
    echo "Get your DATABASE_URL from:"
    echo "1. Supabase Dashboard → Settings → Database"
    echo "2. Copy the 'Connection string' (URI)"
    echo "3. Run: ./supabase_migrate.sh 'your-connection-string'"
    exit 1
fi

DATABASE_URL="$1"
echo "Database URL: ${DATABASE_URL:0:50}..."

# Run migrations
python -c "
import os
os.environ['DATABASE_URL'] = '$DATABASE_URL'

from app import create_app
from flask_migrate import upgrade

app = create_app('production')
with app.app_context():
    print('Running migrations on Supabase database...')
    try:
        upgrade()
        print('✅ Migrations completed successfully!')
        
        # Verify tables
        from app.extensions import db
        tables = db.engine.table_names()
        print(f'✅ Created {len(tables)} tables:')
        for table in sorted(tables):
            print(f'   - {table}')
            
    except Exception as e:
        print(f'❌ Migration failed: {e}')
        exit(1)
"

echo ""
echo "=== Migration Complete ==="
echo "Your Supabase database is ready!"
echo "You can now deploy to Render without running migrations there."
