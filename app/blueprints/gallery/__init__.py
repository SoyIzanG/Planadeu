"""Gallery blueprint - match highlights and stories."""

from flask import Blueprint

gallery_bp = Blueprint("gallery", __name__)

from app.blueprints.gallery import routes
