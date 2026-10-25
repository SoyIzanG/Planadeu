# Deployment Guide - League Site

## GitHub Setup

1. **Initialize Git Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit - League Site application"
   ```

2. **Create GitHub Repository**
   - Go to GitHub and create new repository named `league-site`
   - Copy the remote URL

3. **Push to GitHub**
   ```bash
   git remote add origin https://github.com/yourusername/league-site.git
   git branch -M main
   git push -u origin main
   ```

## Render Deployment

### Environment Variables Required
Set these in Render Dashboard > Environment:

1. **SECRET_KEY**
   - Generate: `python -c "import secrets; print(secrets.token_hex(32))"`
   - Example: `abc123def456...`

2. **DATABASE_URL** (Supabase)
   - Go to Supabase Project Settings > Database
   - Copy Connection string (URI)
   - Format: `postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`

3. **Cloudinary Credentials**
   - Go to Cloudinary Dashboard > Settings > Access Keys
   - CLOUDINARY_CLOUD_NAME: Your cloud name
   - CLOUDINARY_API_KEY: Your API key
   - CLOUDINARY_API_SECRET: Your API secret

4. **FLASK_ENV**
   - Value: `production`

### Deployment Steps

1. **Connect GitHub to Render**
   - Sign up/login to Render
   - Click "New +" > "Web Service"
   - Connect GitHub repository
   - Select `league-site` repo

2. **Configure Service**
   - Name: `league-site`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --bind 0.0.0.0:$PORT run:app`
   - Health Check Path: `/`
   - **Python Version**: `3.13.0` (specified in runtime.txt)

3. **Set Environment Variables**
   - Add all required variables from above
   - Ensure FLASK_ENV=production

4. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy

### Alternative: Manual Render Config
Use the provided `render-config.yaml` file:
- Copy to `render.yaml` in your repo root
- Render will auto-detect and use this configuration
- Python version automatically set to 3.13.0

### Important: Python Version Compatibility
- **Supported**: Python 3.10-3.13
- **Not Supported**: Python 3.14 (psycopg2-binary compatibility issues)
- **Specified**: Python 3.13.0 in `runtime.txt` and `render-config.yaml`

### Fixing Python 3.14 Issues on Render
If Render still uses Python 3.14 despite `runtime.txt`:

1. **Manual Version Setting**:
   - Go to Render Dashboard > Service > Environment
   - Add environment variable: `PYTHON_VERSION=3.13.0`
   - Redeploy the service

2. **Alternative: Use .python-version file**:
   ```bash
   echo "3.13.0" > .python-version
   git add .python-version
   git commit -m "Force Python 3.13.0"
   ```

3. **Contact Render Support**:
   - Render may need to manually set Python version
   - Reference the psycopg2-binary compatibility issue

## Docker Deployment (Optional)

1. **Build Docker Image**
   ```bash
   docker build -t league-site .
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

## Post-Deployment Checklist

- [ ] Database migrations run automatically
- [ ] Upload directories created
- [ ] Environment variables set
- [ ] Health checks passing
- [ ] SSL certificate active
- [ ] Custom domain configured (if needed)
- [ ] **CRITICAL**: Database tables exist (run migrations manually if needed)

## Database Migration Issues

### Best Solution: Run Migrations Locally

**Why Local Migration is Better:**
- ✅ Full control over the process
- ✅ Faster than Render's free tier
- ✅ Easy debugging and troubleshooting
- ✅ Works with free Render tier

### Step-by-Step Local Migration:

1. **Get Supabase DATABASE_URL**:
   - Supabase Dashboard → Settings → Database
   - Copy "Connection string" (URI)

2. **Run Migration Script**:
   ```bash
   # Windows (Recommended)
   supabase_migrate.bat "your-database-url-here"
   
   # Or manual Python command
   python -c "
   import os
   os.environ['DATABASE_URL'] = 'your-database-url-here'
   from app import create_app
   from flask_migrate import upgrade
   app = create_app('production')
   with app.app_context():
       upgrade()
   "
   ```

3. **Verify Success**:
   - Check for "✅ Migrations completed successfully!"
   - Confirm tables are created

4. **Deploy to Render**:
   - Push to GitHub
   - Redeploy (no migration needed)
   - Site should work immediately

### If You See 500 Errors:
The most common issue after deployment is missing database tables.

**Quick Fix:**
1. Run local migration first (see above)
2. Go to Render Dashboard → Service → Shell
3. Run: `cd /opt/render/project/src`
4. Execute migration command (see MIGRATE_FIX.md)

**Automatic Fix:**
- Updated `render-config.yaml` includes automatic migration
- Redeploy to run migrations during build

**Manual Check:**
```bash
# In Render shell
python -c "
from app import create_app
from flask_migrate import current
app = create_app('production')
with app.app_context():
    print('Current migration:', current())
"
```

## Local Development Setup

1. **Copy Environment File**
   ```bash
   cp .env.example .env
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize Database**
   ```bash
   flask init-db
   ```

4. **Run Development Server**
   ```bash
   flask run
   ```

## Troubleshooting

### Common Issues

1. **Python 3.14 Compatibility Error**
   - **Problem**: SQLAlchemy/Alembic not compatible with Python 3.14
   - **Solution**: Ensure `runtime.txt` specifies `python-3.13.0`
   - **Alternative**: Set Python version manually in Render dashboard

2. **Database Connection Errors**
   - Verify DATABASE_URL format
   - Check Supabase project is active
   - Ensure connection string uses `postgresql://` not `postgres://`

3. **Build Failures**
   - Check requirements.txt for correct versions
   - Verify Python version compatibility
   - Check for syntax errors

4. **Environment Variables**
   - Ensure all required variables are set
   - Check for typos in variable names
   - Restart service after changes

5. **Static Files Not Loading**
   - Verify upload directories exist
   - Check file permissions
   - Ensure Cloudinary credentials are correct

## Security Notes

- Never commit `.env` files to version control
- Use strong, randomly generated SECRET_KEY
- Rotate API keys periodically
- Enable SSL in production
- Keep dependencies updated
