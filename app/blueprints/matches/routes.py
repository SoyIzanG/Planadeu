"""
Matches routes - fixtures list, match detail.
"""

from datetime import datetime

from flask import abort, jsonify, render_template, url_for
from app.blueprints.matches import matches_bp
from app.models import Match, MatchEvent, Season


def _active_season():
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        season = Season.query.order_by(Season.start_date.desc()).first()
    return season


@matches_bp.route("/")
def list_matches():
    """Show every stored matchday for the active season."""
    season = _active_season()
    matches = []
    by_matchday = {}
    if season:
        matches = (
            Match.query.filter_by(season_id=season.id)
            .filter(Match.matchday >= 5)
            .filter(Match.kickoff >= datetime(2026, 10, 31))
            .order_by(Match.matchday.asc(), Match.kickoff.asc(), Match.id.asc())
            .all()
        )
        for match in matches:
            by_matchday.setdefault(match.matchday, []).append(match)

    return render_template(
        "matches/list.html",
        season=season,
        matches=matches,
        by_matchday=by_matchday,
        featured_matchday=None,
    )


@matches_bp.route("/api/results")
def results_api():
    """Published match results for opt-in browser notifications."""
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        season = Season.query.order_by(Season.start_date.desc()).first()
    if not season:
        return jsonify([])

    matches = Match.query.filter_by(season_id=season.id).filter(
        Match.matchday >= 5,
        Match.is_played.is_(True),
        Match.home_goals.isnot(None),
        Match.away_goals.isnot(None),
    ).order_by(Match.kickoff.desc()).all()

    return jsonify([{
        "id": match.id,
        "home": match.home_team.name,
        "away": match.away_team.name,
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "signature": f"{match.home_goals}-{match.away_goals}",
        "url": url_for("matches.detail", match_id=match.id),
    } for match in matches])


@matches_bp.route("/<int:match_id>")
def detail(match_id):
    """Match detail with events timeline."""
    match = Match.query.get_or_404(match_id)
    if not match.matchday or match.matchday < 5 or not match.kickoff or match.kickoff < datetime(2026, 10, 31):
        abort(404)
    events = match.events.order_by(MatchEvent.minute).all()
    return render_template(
        "matches/detail.html",
        match=match,
        events=events,
    )
