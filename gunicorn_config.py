
"""
Gunicorn configuration for production deployment.
"""

import os

# Bind to Render's assigned port
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Use a single worker to reduce memory consumption
workers = 1
worker_class = "sync"

# Timeouts
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Process naming
proc_name = "league_site"

# Application
wsgi_app = "run:app"