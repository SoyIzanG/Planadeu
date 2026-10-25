"""
Gunicorn configuration for production deployment.
"""

import multiprocessing
import os

# Bind
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# Workers
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000

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
