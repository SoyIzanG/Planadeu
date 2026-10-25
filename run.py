"""
Application entry point for local development.
Production: use gunicorn -c gunicorn_config.py run:app
"""

import os
from app import create_app

# Config from environment
config_name = os.environ.get("FLASK_ENV", "development")
if config_name == "production":
    config_name = "production"
elif config_name == "testing":
    config_name = "testing"
else:
    config_name = "development"

app = create_app(config_name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=config_name == "development")
