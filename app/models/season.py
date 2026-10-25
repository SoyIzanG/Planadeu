"""
Season model - represents a league season.
"""

from app.extensions import db


class Season(db.Model):
    """League season (e.g., 2024-2025)."""
    
    __tablename__ = "seasons"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "2024-2025"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships
    teams = db.relationship(
        "Team",
        secondary="season_teams",
        back_populates="seasons",
        lazy="dynamic",
    )
    matches = db.relationship("Match", back_populates="season", lazy="dynamic")
    standings = db.relationship("Standing", back_populates="season", lazy="dynamic")
    
    def __repr__(self):
        return f"<Season {self.name}>"


# Association table for many-to-many: Season <-> Team
season_teams = db.Table(
    "season_teams",
    db.Column("season_id", db.Integer, db.ForeignKey("seasons.id"), primary_key=True),
    db.Column("team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True),
)
