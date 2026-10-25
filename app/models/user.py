"""
User and Role models for authentication and authorization.
"""

from datetime import datetime
from flask_login import UserMixin

from app.extensions import db, bcrypt


class Role(db.Model):
    """User role for permission-based access control."""
    
    __tablename__ = "roles"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    # Relationship
    users = db.relationship("User", back_populates="role", lazy="dynamic")
    
    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    """Admin/Staff user for league management."""
    
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign key
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    
    # Relationships
    role = db.relationship("Role", back_populates="users")
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")
    
    # Password property
    @property
    def password(self):
        raise AttributeError("Password is not a readable attribute")
    
    @password.setter
    def password(self, value):
        self.password_hash = bcrypt.generate_password_hash(value).decode("utf-8")
    
    def check_password(self, password: str) -> bool:
        """Verify password against hash."""
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has specific role."""
        return self.role and self.role.name == role_name
    
    def is_admin(self) -> bool:
        """Check if user has Admin role."""
        return self.has_role("Admin")
    
    def is_stats_manager(self) -> bool:
        """Check if user has Stats Manager role."""
        return self.has_role("Stats Manager") or self.is_admin()
    
    def __repr__(self):
        return f"<User {self.username}>"
