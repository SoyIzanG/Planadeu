# Manual Database Migration for Render

## Quick Fix - Run Migrations Manually

If your site is live but showing 500 errors due to missing database tables:

### Option 1: Render Shell (Recommended)
1. Go to Render Dashboard → your service → "Shell" tab
2. Run this command:
```bash
cd /opt/render/project/src
python -c "
from app import create_app
from flask_migrate import upgrade
app = create_app('production')
with app.app_context():
    upgrade()
print('Migrations completed!')
"
```

### Option 2: Update Build Process
1. Push the updated `render-config.yaml` (already includes migration script)
2. Trigger new deployment
3. Migrations will run automatically during build

### Option 3: Environment Variable Check
Make sure these are set in Render Dashboard:
- `DATABASE_URL` - Your Supabase connection string
- `SECRET_KEY` - Generated secret key
- `FLASK_ENV=production`

### Verification
After running migrations, your site should work without 500 errors.
Check the logs to confirm "Migrations completed successfully!" message.
