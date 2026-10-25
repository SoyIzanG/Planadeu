"""REST API blueprint - JSON endpoints."""

from flask import Blueprint

api_bp = Blueprint("api", __name__)

from app.api import routes
