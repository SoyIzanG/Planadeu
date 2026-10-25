@echo off
REM Supabase Migration Script for Windows

if "%~1"=="" (
    echo Usage: supabase_migrate.bat ^<DATABASE_URL^>
    echo.
    echo Get your DATABASE_URL from:
    echo 1. Supabase Dashboard -^> Settings -^> Database
    echo 2. Copy the 'Connection string' ^(URI^)
    echo 3. Run: supabase_migrate.bat "your-connection-string"
    pause
    exit /b 1
)

echo === Supabase Database Migration ===
echo.
echo Database URL: %~1

REM Run migrations
python -c "
import os
os.environ['DATABASE_URL'] = '%~1'

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

echo.
echo === Migration Complete ===
echo Your Supabase database is ready!
echo You can now deploy to Render without running migrations there.
pause
