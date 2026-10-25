"""
Gallery routes - public view of match highlights and stories.
"""

from flask import render_template, request, current_app
from app.blueprints.gallery import gallery_bp
from app.models import Gallery, Match
from app.extensions import db
from sqlalchemy import or_


@gallery_bp.route("/")
def index():
    """Gallery home page with all items."""
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "")
    search = request.args.get("q", "").strip()
    
    q = Gallery.query
    
    # Filter by category
    if category:
        q = q.filter_by(category=category)
    
    # Search functionality
    if search:
        q = q.filter(
            or_(
                Gallery.title.ilike(f"%{search}%"),
                Gallery.description.ilike(f"%{search}%")
            )
        )
    
    # Order by featured first, then by creation date (newest first)
    galleries = q.order_by(Gallery.is_featured.desc(), Gallery.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    
    # Get categories for filter
    categories = db.session.query(Gallery.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    return render_template(
        "gallery/index.html",
        galleries=galleries,
        categories=categories,
        current_category=category,
        search=search
    )


@gallery_bp.route("/<int:gallery_id>")
def detail(gallery_id):
    """Gallery item detail page."""
    gallery = Gallery.query.get_or_404(gallery_id)
    return render_template("gallery/detail.html", gallery=gallery)


@gallery_bp.route("/highlights")
def highlights():
    """Match highlights gallery."""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    
    q = Gallery.query.filter_by(category="highlight")
    
    if search:
        q = q.filter(
            or_(
                Gallery.title.ilike(f"%{search}%"),
                Gallery.description.ilike(f"%{search}%")
            )
        )
    
    galleries = q.order_by(Gallery.is_featured.desc(), Gallery.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    
    return render_template(
        "gallery/highlights.html",
        galleries=galleries,
        search=search
    )


@gallery_bp.route("/stories")
def stories():
    """Stories gallery."""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    
    q = Gallery.query.filter_by(category="story")
    
    if search:
        q = q.filter(
            or_(
                Gallery.title.ilike(f"%{search}%"),
                Gallery.description.ilike(f"%{search}%")
            )
        )
    
    galleries = q.order_by(Gallery.is_featured.desc(), Gallery.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    
    return render_template(
        "gallery/stories.html",
        galleries=galleries,
        search=search
    )
