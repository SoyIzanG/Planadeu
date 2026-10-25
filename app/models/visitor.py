"""
Visitor tracking model for analytics.
"""

from datetime import datetime
from app.extensions import db


class Visitor(db.Model):
    """Track unique visitors and page views."""
    
    __tablename__ = "visitors"
    
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    user_agent = db.Column(db.Text)
    page_visited = db.Column(db.String(255), nullable=False)
    first_visit = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_visit = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    visit_count = db.Column(db.Integer, default=1, nullable=False)
    is_unique = db.Column(db.Boolean, default=True, nullable=False)
    
    @property
    def visit_frequency(self):
        """Return visit frequency description."""
        if self.visit_count == 1:
            return "First time"
        elif self.visit_count <= 5:
            return "Occasional"
        elif self.visit_count <= 20:
            return "Regular"
        else:
            return "Frequent"
    
    def __repr__(self):
        return f"<Visitor {self.ip_address} - {self.visit_count} visits>"
