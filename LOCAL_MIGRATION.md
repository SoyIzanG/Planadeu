# Local Migration with Supabase Database

## Step 1: Get Your Supabase DATABASE_URL

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Go to **Settings** → **Database**
4. Scroll down to **Connection string**
5. Copy the **URI** (looks like this):
```
postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

## Step 2: Set Environment Variable Locally

### Option A: Temporary Environment Variable (Recommended)
```bash
# In your terminal
export DATABASE_URL="your-supabase-connection-string-here"
```

### Option B: Create .env File
```bash
# Create .env file in project root
echo "DATABASE_URL=your-supabase-connection-string-here" > .env
```

## Step 3: Run Migrations Locally

```bash
# Navigate to project
cd "c:\Users\USER\Desktop\Junate World\League_Site"

# Run migrations
python -c "
from app import create_app
from flask_migrate import upgrade
import os

app = create_app('production')
with app.app_context():
    print('Running migrations on Supabase database...')
    print(f'Database URL: {os.getenv(\"DATABASE_URL\", \"Not set\")}')
    try:
        upgrade()
        print('✅ Migrations completed successfully!')
        print('Your Supabase database now has all tables.')
    except Exception as e:
        print(f'❌ Migration error: {e}')
        exit(1)
"
```

## Step 4: Verify Tables Created

```bash
# Check if tables exist
python -c "
from app import create_app
from app.extensions import db
from app.models import User, Season, Team, Player, Match, FanComment

app = create_app('production')
with app.app_context():
    tables = db.engine.table_names()
    print('Tables in database:')
    for table in sorted(tables):
        print(f'  ✅ {table}')
    print(f'Total tables: {len(tables)}')
"
```

## Step 5: Deploy to Render

After successful local migration:

1. **Push changes** to GitHub
2. **Redeploy** on Render (no need to run migrations there)
3. **Test** the live site

## Benefits of Local Migration

✅ **Full Control**: See exactly what's happening
✅ **Faster**: No waiting for Render build process
✅ **Debugging**: Easy to fix any issues locally
✅ **Free Tier Friendly**: No additional Render resources needed
✅ **Safety**: Can rollback if needed

## Troubleshooting

### Connection Issues
- **Invalid URL**: Double-check Supabase connection string
- **Password Wrong**: Regenerate connection string in Supabase
- **Network Issues**: Try again or check firewall

### Migration Errors
- **Permission Denied**: Check Supabase database permissions
- **Table Exists**: Fresh database needed (drop all tables first)
- **Version Conflicts**: Ensure local SQLAlchemy matches production

### Quick Test
```bash
# Test database connection first
python -c "
import os
from sqlalchemy import create_engine
from app import create_app

app = create_app('production')
with app.app_context():
    try:
        engine = db.engine
        with engine.connect() as conn:
            print('✅ Database connection successful!')
            print(f'Database: {engine.url.database}')
    except Exception as e:
        print(f'❌ Connection failed: {e}')
"
```

This approach is much more reliable than trying to run migrations on Render's free tier!
