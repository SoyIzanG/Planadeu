"""
Application configuration classes for different environments.
Uses environment variables for sensitive/部署-specific settings.
"""

import os
from pathlib import Path


# Base directory for file uploads
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
TEAM_LOGOS_FOLDER = UPLOAD_FOLDER / "team_logos"
PLAYER_PHOTOS_FOLDER = UPLOAD_FOLDER / "player_photos"
GALLERY_FOLDER = UPLOAD_FOLDER / "gallery"


class Config:
    """Base configuration class."""
    
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    
    # Database - overridden in subclasses
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    
    # File uploads
    UPLOAD_FOLDER = str(UPLOAD_FOLDER)
    TEAM_LOGOS_FOLDER = str(TEAM_LOGOS_FOLDER)
    PLAYER_PHOTOS_FOLDER = str(PLAYER_PHOTOS_FOLDER)
    GALLERY_FOLDER = str(GALLERY_FOLDER)
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4MB max upload
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # Cloudinary (production) - set in ProductionConfig
    CLOUDINARY_CLOUD_NAME = None
    CLOUDINARY_API_KEY = None
    CLOUDINARY_API_SECRET = None
    USE_CLOUDINARY = False
    
    # Pagination
    ITEMS_PER_PAGE = 20
    
    # Session
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # Session-based, no time limit
    
    @staticmethod
    def init_app(app):
        """Initialize application with config."""
        # Ensure upload directories exist
        for folder in [UPLOAD_FOLDER, TEAM_LOGOS_FOLDER, PLAYER_PHOTOS_FOLDER, GALLERY_FOLDER]:
            folder.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """Development environment configuration - uses SQLite locally."""
    
    DEBUG = True
    ENV = "development"
    
    # SQLite for local development (no setup required)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + str(BASE_DIR / "league_dev.db"),
    )
    SESSION_COOKIE_SECURE = False  # Allow HTTP in dev


class ProductionConfig(Config):
    """Production environment configuration - uses Supabase (PostgreSQL) and Cloudinary."""
    
    DEBUG = False
    ENV = "production"
    
    SECRET_KEY = os.environ.get("SECRET_KEY")
    USE_CLOUDINARY = True
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
    # Supabase: use connection string from Project Settings > Database
    # Format: postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
    _db_url = os.environ.get("DATABASE_URL")
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url or ""


class TestingConfig(Config):
    """Testing environment configuration."""
    
    TESTING = True
    DEBUG = True
    ENV = "testing"
    
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"


# Configuration registry
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
