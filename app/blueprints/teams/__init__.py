"""Teams blueprint - team profiles, squad."""

from flask import Blueprint

teams_bp = Blueprint("teams", __name__)

from app.blueprints.teams import routes
