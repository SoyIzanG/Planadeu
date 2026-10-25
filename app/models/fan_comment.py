"""
FanComment model - visitor comments for fan engagement.
"""

from datetime import datetime
from app.extensions import db


class FanComment(db.Model):
    """Fan comment model for visitor engagement."""
    
    __tablename__ = 'fan_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(100))  # Optional nickname
    comment = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=True)  # Auto-approve, can be moderated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<FanComment {self.name}: {self.comment[:50]}...>'
    
    @property
    def display_name(self):
        """Get the display name (nickname if provided, otherwise name)."""
        return self.nickname or self.name
    
    @property
    def formatted_date(self):
        """Get formatted creation date."""
        return self.created_at.strftime('%B %d, %Y at %I:%M %p')
