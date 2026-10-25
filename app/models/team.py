"""
Team model - represents a football club.
"""

from app.extensions import db


class Team(db.Model):
    """Football club/team in the league."""
    
    __tablename__ = "teams"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(10))  # e.g., "MUN", "LIV"
    logo_filename = db.Column(db.String(255))
    founded_year = db.Column(db.Integer)
    stadium = db.Column(db.String(100))
    
    # Relationships
    seasons = db.relationship(
        "Season",
        secondary="season_teams",
        back_populates="teams",
        lazy="dynamic",
    )
    players = db.relationship("Player", back_populates="team", lazy="dynamic")
    home_matches = db.relationship(
        "Match",
        foreign_keys="Match.home_team_id",
        back_populates="home_team",
        lazy="dynamic",
    )
    away_matches = db.relationship(
        "Match",
        foreign_keys="Match.away_team_id",
        back_populates="away_team",
        lazy="dynamic",
    )
    
    def __repr__(self):
        return f"<Team {self.name}>"
