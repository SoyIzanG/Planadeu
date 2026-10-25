"""
Match model - represents a football fixture.
"""

from datetime import datetime
from app.extensions import db


class Match(db.Model):
    """Football match/fixture between two teams."""
    
    __tablename__ = "matches"
    
    id = db.Column(db.Integer, primary_key=True)
    matchday = db.Column(db.Integer, nullable=False)  # Round number
    kickoff = db.Column(db.DateTime, nullable=False)
    
    # Scores
    home_goals = db.Column(db.Integer, default=None)  # None = not played
    away_goals = db.Column(db.Integer, default=None)
    
    # Status
    is_played = db.Column(db.Boolean, default=False, nullable=False)
    played_at = db.Column(db.DateTime)  # When result was recorded
    
    # Foreign keys
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    
    # Relationships
    season = db.relationship("Season", back_populates="matches")
    home_team = db.relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = db.relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    events = db.relationship(
        "MatchEvent",
        back_populates="match",
        lazy="dynamic",
        order_by="MatchEvent.minute",
    )
    
    @property
    def score_display1(self):
        """Display score or vs for unplayed matches."""
        if self.is_played and self.home_goals is not None and self.away_goals is not None:
            return f"{self.home_goals}<br>{self.away_goals}"
        return "vs"
    
    @property
    def score_display(self):
        """Display score or vs for unplayed matches."""
        if self.is_played and self.home_goals is not None and self.away_goals is not None:
            return f"{self.home_goals} - {self.away_goals}"
        return "vs"
    
    def get_winner_id(self):
        """Return winning team id, or None for draw."""
        if not self.is_played or self.home_goals is None:
            return None
        if self.home_goals > self.away_goals:
            return self.home_team_id
        if self.away_goals > self.home_goals:
            return self.away_team_id
        return None
    
    def __repr__(self):
        return f"<Match {self.home_team_id} vs {self.away_team_id} ({self.matchday})>"
