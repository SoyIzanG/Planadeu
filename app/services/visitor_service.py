"""
Visitor tracking service for analytics.
"""

from datetime import datetime, timedelta
from flask import request, g
from app.extensions import db
from app.models import Visitor


def track_visitor():
    """Track visitor information."""
    try:
        # Get visitor information
        ip_address = get_client_ip()
        user_agent = request.headers.get('User-Agent', 'Unknown')
        page_visited = request.endpoint or 'unknown'
        
        # Check if visitor exists
        existing_visitor = Visitor.query.filter_by(
            ip_address=ip_address,
            page_visited=page_visited
        ).first()
        
        if existing_visitor:
            # Update existing visitor
            existing_visitor.last_visit = datetime.utcnow()
            existing_visitor.visit_count += 1
            existing_visitor.is_unique = False  # Not unique on subsequent visits
        else:
            # Create new visitor record
            visitor = Visitor(
                ip_address=ip_address,
                user_agent=user_agent,
                page_visited=page_visited,
                first_visit=datetime.utcnow(),
                last_visit=datetime.utcnow(),
                visit_count=1,
                is_unique=True
            )
            db.session.add(visitor)
        
        db.session.commit()
        
        # Store in g for potential use in templates
        g.visitor_tracked = True
        
    except Exception:
        # Don't let tracking errors break the app
        db.session.rollback()
        pass


def get_visitor_stats():
    """Get visitor statistics."""
    try:
        # Total unique visitors
        total_unique = Visitor.query.filter_by(is_unique=True).count()
        
        # Total visits
        total_visits = db.session.query(db.func.sum(Visitor.visit_count)).scalar() or 0
        
        # Today's stats
        today = datetime.utcnow().date()
        today_visitors = Visitor.query.filter(
            db.func.date(Visitor.first_visit) == today
        ).count()
        
        today_unique = Visitor.query.filter(
            db.func.date(Visitor.first_visit) == today,
            Visitor.is_unique == True
        ).count()
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_visitors = Visitor.query.filter(
            Visitor.last_visit >= week_ago
        ).count()
        
        # Top pages
        top_pages = db.session.query(
            Visitor.page_visited,
            db.func.count(Visitor.id).label('visits')
        ).group_by(Visitor.page_visited).order_by(
            db.func.count(Visitor.id).desc()
        ).limit(10).all()
        
        return {
            'total_unique': total_unique,
            'total_visits': total_visits,
            'today_visitors': today_visitors,
            'today_unique': today_unique,
            'recent_visitors': recent_visitors,
            'top_pages': top_pages,
        }
        
    except Exception:
        return {
            'total_unique': 0,
            'total_visits': 0,
            'today_visitors': 0,
            'today_unique': 0,
            'recent_visitors': 0,
            'top_pages': [],
        }


def get_client_ip():
    """Get client IP address, considering proxies."""
    # Check for forwarded IP headers
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    
    if request.headers.get('X-Client-IP'):
        return request.headers.get('X-Client-IP')
    
    # Fall back to remote address
    return request.remote_addr or '0.0.0.0'
