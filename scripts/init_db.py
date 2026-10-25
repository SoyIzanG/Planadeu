"""
Initialize database with seed data.
Run: flask shell < scripts/init_db.py
Or: python -c "from app import create_app; from scripts.init_db import run; app = create_app(); run(app)"
"""


def run(app):
    """Create tables and seed Admin role."""
    from app.extensions import db
    from app.models import Role

    with app.app_context():
        db.create_all()
        if not Role.query.filter_by(name="Admin").first():
            db.session.add(Role(name="Admin"))
        if not Role.query.filter_by(name="Stats Manager").first():
            db.session.add(Role(name="Stats Manager"))
        db.session.commit()
        print("Database initialized with roles.")
