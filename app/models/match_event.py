"""
MatchEvent model - goals, cards, substitutions.
"""

from app.extensions import db


class MatchEvent(db.Model):
    """Match event: goal, yellow card, red card, substitution."""
    
    __tablename__ = "match_events"
    
    # Event types
    TYPE_GOAL = "goal"
    TYPE_YELLOW = "yellow"
    TYPE_RED = "red"
    TYPE_SUBSTITUTION = "substitution"
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(20), nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    extra_time = db.Column(db.Integer)  # Stoppage time, e.g. 90+3
    
    # For goals
    is_penalty = db.Column(db.Boolean, default=False)
    is_own_goal = db.Column(db.Boolean, default=False)
    
    # Foreign keys
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)  # Primary player
    goal_scorer_id = db.Column(db.Integer, db.ForeignKey("players.id"))  # For own goals: scorer is different
    assist_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    
    # For substitutions
    player_off_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    player_on_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    
    # Relationships
    match = db.relationship("Match", back_populates="events")
    player = db.relationship("Player", foreign_keys=[player_id])
    goal_scorer = db.relationship(
        "Player",
        foreign_keys=[goal_scorer_id],
        back_populates="goals_scored",
    )
    assist = db.relationship(
        "Player",
        foreign_keys=[assist_id],
        back_populates="assists_given",
    )
    player_off = db.relationship(
        "Player",
        foreign_keys=[player_off_id],
    )
    player_on = db.relationship(
        "Player",
        foreign_keys=[player_on_id],
    )
    
    def __repr__(self):
        return f"<MatchEvent {self.event_type} @ {self.minute}'>"
