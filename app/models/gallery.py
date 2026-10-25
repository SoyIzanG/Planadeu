"""
Gallery model for match highlights and stories.
"""

from datetime import datetime
from app.extensions import db


class Gallery(db.Model):
    """Gallery model for match highlights and stories."""
    
    __tablename__ = 'galleries'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_filename = db.Column(db.String(255))
    category = db.Column(db.String(50), nullable=False, default='highlight')  # highlight, story, event
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=True)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    match = db.relationship('Match', backref='galleries')
    
    def __repr__(self):
        return f'<Gallery {self.title}>'
    
    @property
    def image_url(self):
        """Get the image URL for the gallery item."""
        if self.image_filename:
            if self.image_filename.startswith(('http://', 'https://')):
                return self.image_filename
            return f'/uploads/gallery/{self.image_filename}'
        return None
