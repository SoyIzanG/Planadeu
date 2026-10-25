"""
Standing model - league table position for a team in a season.
"""

from app.extensions import db


class Standing(db.Model):
    """
    League table standing for a team in a season.
    Auto-calculated by standings service. previous_position for tracking changes.
    """
    
    __tablename__ = "standings"
    
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, nullable=False)
    previous_position = db.Column(db.Integer)  # For position change indicator
    
    # Stats
    played = db.Column(db.Integer, default=0, nullable=False)
    won = db.Column(db.Integer, default=0, nullable=False)
    drawn = db.Column(db.Integer, default=0, nullable=False)
    lost = db.Column(db.Integer, default=0, nullable=False)
    goals_for = db.Column(db.Integer, default=0, nullable=False)
    goals_against = db.Column(db.Integer, default=0, nullable=False)
    goal_difference = db.Column(db.Integer, default=0, nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)
    
    # Form: last 5 matches as string e.g. "WWDLW"
    form = db.Column(db.String(5), default="")
    
    # Foreign keys
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    
    # Relationships
    season = db.relationship("Season", back_populates="standings")
    team = db.relationship("Team", backref="standings_list")
    
    # Unique constraint: one standing per team per season
    __table_args__ = (
        db.UniqueConstraint("season_id", "team_id", name="uq_standing_season_team"),
    )
    
    @property
    def position_change(self):
        """Return position change: positive = moved up, negative = moved down."""
        if self.previous_position is None:
            return None
        return self.previous_position - self.position
    
    def __repr__(self):
        return f"<Standing #{self.position} {self.team_id} Pts:{self.points}>"
