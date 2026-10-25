"""
Seed test data for local development.
Run: python scripts/seed_test_data.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models import Role, User, Season, Team


def seed():
    app = create_app()
    with app.app_context():
        # Roles
        admin_role = Role.query.filter_by(name="Admin").first()
        if not admin_role:
            admin_role = Role()
            admin_role.name = "Admin"
            db.session.add(admin_role)
            db.session.commit()
            print("Created Admin role")

        stats_role = Role.query.filter_by(name="Stats Manager").first()
        if not stats_role:
            stats_role = Role()
            stats_role.name = "Stats Manager"
            db.session.add(stats_role)
            db.session.commit()
            print("Created Stats Manager role")

        # Admin user
        if not User.query.filter_by(email="admin@test.com").first():
            user = User()
            user.email = "admin@test.com"
            user.username = "admin"
            user.role_id = admin_role.id
            user.password = "admin123"
            db.session.add(user)
            db.session.commit()
            print("Created admin user (admin@test.com / admin123)")

        # Season
        season = Season.query.filter_by(name="2024-2025").first()
        if not season:
            from datetime import date
            season = Season()
            season.name = "2024-2025"
            season.start_date = date(2024, 8, 1)
            season.end_date = date(2025, 5, 31)
            season.is_active = True
            db.session.add(season)
            db.session.commit()
            print("Created season 2024-2025")

        # Teams
        team_names = ["Arsenal", "Chelsea", "Liverpool", "Manchester City", "Manchester United"]
        for name in team_names:
            if not Team.query.filter_by(name=name).first():
                t = Team()
                t.name = name
                t.short_name = name[:3].upper() if len(name) >= 3 else name
                db.session.add(t)
        db.session.commit()
        print("Created teams")

        # Add teams to season
        season = Season.query.filter_by(name="2024-2025").first()
        for team in Team.query.all():
            if team not in season.teams:
                season.teams.append(team)
        db.session.commit()
        print("Added teams to season")

        print("\nSeed complete! Login: admin@test.com / admin123")


if __name__ == "__main__":
    seed()
