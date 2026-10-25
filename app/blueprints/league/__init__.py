"""League blueprint - table, stats, homepage."""

from flask import Blueprint

league_bp = Blueprint("league", __name__)

from app.blueprints.league import routes
