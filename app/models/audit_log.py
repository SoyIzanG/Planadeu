"""
AuditLog model - tracks admin actions for accountability.
"""

from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    """Audit log entry for admin actions."""
    
    __tablename__ = "audit_logs"
    
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))  # Team, Player, Match, etc.
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)  # JSON or text description
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign key
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    # Relationships
    user = db.relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id}>"
