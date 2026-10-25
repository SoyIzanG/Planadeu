"""Players blueprint - player profiles."""

from flask import Blueprint

players_bp = Blueprint("players", __name__)

from app.blueprints.players import routes
