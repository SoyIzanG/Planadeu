"""
Custom decorators for role-based access control.
"""

from functools import wraps
from flask import abort
from flask_login import current_user


def admin_required(f):
    """Require Admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def stats_manager_required(f):
    """Require Stats Manager or Admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_stats_manager():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def login_required(f):
    """Require any authenticated user. Use Flask-Login's built-in normally."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        return f(*args, **kwargs)
    return decorated
