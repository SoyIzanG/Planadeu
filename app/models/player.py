"""
Player model - represents a football player.
"""

from app.extensions import db


class Player(db.Model):
    """Football player registered to a team."""
    
    __tablename__ = "players"
    
    # Position constants
    POSITION_GOALKEEPER = "GK"
    POSITION_DEFENDER = "DEF"
    POSITION_MIDFIELDER = "MID"
    POSITION_FORWARD = "FWD"
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    photo_filename = db.Column(db.String(255))
    position = db.Column(db.String(10), nullable=False)  # GK, DEF, MID, FWD
    jersey_number = db.Column(db.Integer)
    age = db.Column(db.Integer)  # Player's age
    
    # Stats (denormalized for quick access - updated by match service)
    goals = db.Column(db.Integer, default=0, nullable=False)
    assists = db.Column(db.Integer, default=0, nullable=False)
    yellow_cards = db.Column(db.Integer, default=0, nullable=False)
    red_cards = db.Column(db.Integer, default=0, nullable=False)
    appearances = db.Column(db.Integer, default=0, nullable=False)
    clean_sheets = db.Column(db.Integer, default=0, nullable=False)  # For GK/DEF
    
    # Foreign key
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    
    # Relationships
    team = db.relationship("Team", back_populates="players")
    
    # Match events (goals, assists, cards) - for detailed tracking
    goals_scored = db.relationship(
        "MatchEvent",
        foreign_keys="MatchEvent.goal_scorer_id",
        back_populates="goal_scorer",
        lazy="dynamic",
    )
    assists_given = db.relationship(
        "MatchEvent",
        foreign_keys="MatchEvent.assist_id",
        back_populates="assist",
        lazy="dynamic",
    )
    
    @property
    def full_name(self):
        """Full name display."""
        return f"{self.first_name} {self.last_name}"
    
    def is_goalkeeper_or_defender(self) -> bool:
        """Check if player qualifies for clean sheet stat."""
        return self.position in (self.POSITION_GOALKEEPER, self.POSITION_DEFENDER)
    
    def __repr__(self):
        return f"<Player {self.full_name}>"
