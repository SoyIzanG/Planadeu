"""
Matches routes - fixtures list, match detail.
"""

from flask import render_template, request
from app.blueprints.matches import matches_bp
from app.models import Match, MatchEvent, Season


@matches_bp.route("/")
def list_matches():
    """Fixtures and results list."""
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        season = Season.query.order_by(Season.start_date.desc()).first()

    matches = []
    if season:
        matchday = request.args.get("matchday", type=int)
        q = Match.query.filter_by(season_id=season.id).order_by(Match.matchday, Match.kickoff)
        if matchday:
            q = q.filter_by(matchday=matchday)
        matches = q.all()

    # Group by matchday
    by_matchday = {}
    for m in matches:
        by_matchday.setdefault(m.matchday, []).append(m)

    return render_template(
        "matches/list.html",
        season=season,
        matches=matches,
        by_matchday=by_matchday,
    )


@matches_bp.route("/<int:match_id>")
def detail(match_id):
    """Match detail with events timeline."""
    match = Match.query.get_or_404(match_id)
    events = match.events.order_by(MatchEvent.minute).all()
    return render_template(
        "matches/detail.html",
        match=match,
        events=events,
    )
