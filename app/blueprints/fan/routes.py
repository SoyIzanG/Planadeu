"""
Fan base routes - visitor comments and engagement.
"""

from flask import render_template, request, redirect, url_for, flash
from app.blueprints.fan import fan_bp
from app.models import FanComment
from app.extensions import db


@fan_bp.route("/")
def index():
    """Fan base home page with comments."""
    page = request.args.get("page", 1, type=int)
    
    # Get approved comments, newest first
    comments = FanComment.query.filter_by(is_approved=True).order_by(
        FanComment.created_at.desc()
    ).paginate(
        page=page,
        per_page=20,
        error_out=False,
    )
    
    return render_template(
        "fan/index.html",
        comments=comments,
    )


@fan_bp.route("/comment", methods=["POST"])
def add_comment():
    """Add a new fan comment."""
    name = request.form.get("name", "").strip()
    nickname = request.form.get("nickname", "").strip()
    comment = request.form.get("comment", "").strip()
    
    # Validation
    if not name or not comment:
        flash("Name and comment are required.", "danger")
        return redirect(url_for("fan.index"))
    
    if len(name) > 100:
        flash("Name is too long (max 100 characters).", "danger")
        return redirect(url_for("fan.index"))
    
    if len(nickname) > 100:
        flash("Nickname is too long (max 100 characters).", "danger")
        return redirect(url_for("fan.index"))
    
    if len(comment) < 10:
        flash("Comment must be at least 10 characters long.", "danger")
        return redirect(url_for("fan.index"))
    
    if len(comment) > 1000:
        flash("Comment is too long (max 1000 characters).", "danger")
        return redirect(url_for("fan.index"))
    
    # Create comment
    fan_comment = FanComment(
        name=name,
        nickname=nickname if nickname else None,
        comment=comment,
        is_approved=True  # Auto-approve, can be moderated by admin
    )
    
    db.session.add(fan_comment)
    db.session.commit()
    
    flash("Thank you for your comment! It has been posted successfully.", "success")
    return redirect(url_for("fan.index"))
