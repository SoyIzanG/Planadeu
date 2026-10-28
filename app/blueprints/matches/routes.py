"""
Matches routes - fixtures list, match detail.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import jsonify, render_template, request, url_for, redirect
from flask_login import current_user
from app.blueprints.matches import matches_bp
from app.models import Match, MatchEvent, Season


MADRID = ZoneInfo("Europe/Madrid")


def _featured_matchday(season_id: int, now: datetime | None = None) -> int | None:
    """Choose one featured round without deleting/hiding fixtures from storage.

    Until Tuesday 15:00 Madrid time, keep the most recently started round featured.
    From Tuesday 15:00 onward, feature the next upcoming round.
    """
    now = now or datetime.now(MADRID)
    local_now = now.astimezone(MADRID) if now.tzinfo else now
    naive_now = local_now.replace(tzinfo=None)

    query = Match.query.filter_by(season_id=season_id)
    latest_started = (
        query.filter(Match.kickoff <= naive_now)
        .order_by(Match.kickoff.desc(), Match.matchday.desc())
        .first()
    )
    next_upcoming = (
        query.filter(Match.kickoff >= naive_now)
        .order_by(Match.kickoff.asc(), Match.matchday.asc())
        .first()
    )

    # Tuesday (weekday 1) through 14:59:59: keep the previous/current round.
    before_cutoff = local_now.weekday() < 1 or (
        local_now.weekday() == 1
        and (local_now.hour, local_now.minute, local_now.second) < (15, 0, 0)
    )
    if before_cutoff and latest_started:
        return latest_started.matchday
    if next_upcoming:
        return next_upcoming.matchday
    # If no future fixtures exist (end of season), keep the latest round visible.
    return latest_started.matchday if latest_started else None


@matches_bp.route("/")
def list_matches():
    """Show only the featured matchday; other rounds remain stored."""
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        season = Season.query.order_by(Season.start_date.desc()).first()

    matches = []
    featured_matchday = None
    if season:
        featured_matchday = _featured_matchday(season.id)
        if featured_matchday is not None:
            matches = (
                Match.query.filter_by(
                    season_id=season.id,
                    matchday=featured_matchday,
                )
                .order_by(Match.kickoff, Match.id)
                .all()
            )

    by_matchday = {}
    if featured_matchday is not None:
        # Keep the existing display label for the provisional round mapping.
        display_matchday = 1 if featured_matchday == 5 else featured_matchday
        by_matchday[display_matchday] = matches

    return render_template(
        "matches/list.html",
        season=season,
        matches=matches,
        by_matchday=by_matchday,
        featured_matchday=featured_matchday,
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
