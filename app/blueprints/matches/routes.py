"""
Matches routes - fixtures list, match detail.
"""

from flask import jsonify, render_template, request, url_for, redirect
from flask_login import current_user
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
            # La jornada que estaba numerada como 5 pasa a ser la jornada 1.
            if matchday == 1:
                q = q.filter(Match.matchday.in_([1, 5]))
            elif matchday != 5:
                q = q.filter_by(matchday=matchday)
        matches = q.all()

    # Mostrar la antigua jornada 5 como jornada 1.
    by_matchday = {}
    for m in matches:
        display_matchday = 1 if m.matchday == 5 else m.matchday
        by_matchday.setdefault(display_matchday, []).append(m)

    return render_template(
        "matches/list.html",
        season=season,
        matches=matches,
        by_matchday=by_matchday,
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
    events = match.events.order_by(MatchEvent.minute).all()
    return render_template(
        "matches/detail.html",
        match=match,
        events=events,
    )
