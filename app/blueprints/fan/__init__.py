"""Fan base blueprint - visitor comments and engagement."""

from flask import Blueprint

fan_bp = Blueprint("fan", __name__)

from app.blueprints.fan import routes
