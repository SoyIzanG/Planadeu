"""Matches blueprint - fixtures, results."""

from flask import Blueprint

matches_bp = Blueprint("matches", __name__)

from app.blueprints.matches import routes
