"""
Matches routes - fixtures list, match detail.
"""

from datetime import datetime
import csv
from io import StringIO
from zoneinfo import ZoneInfo

from flask import Response, jsonify, render_template, request, url_for, redirect
from flask_login import current_user
from app.blueprints.matches import matches_bp
from app.models import Match, MatchEvent, Season


MADRID = ZoneInfo("Europe/Madrid")


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


@matches_bp.route("/export")
def export_matches():
    """Download all season matchdays as a CSV spreadsheet."""
    season = _active_season()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Jornada", "Fecha", "Hora", "Local", "Visitante", "Resultado", "Estado de la hora"])

    if season:
        matches = (
            Match.query.filter_by(season_id=season.id)
            .order_by(Match.matchday.asc(), Match.kickoff.asc(), Match.id.asc())
            .all()
        )
        for match in matches:
            kickoff = match.kickoff
            time_pending = (
                match.home_team.name == "UE Planadeu"
                or match.away_team.name == "UE Planadeu"
                or not match.kickoff_confirmed
                or (kickoff and kickoff.strftime("%H:%M") == "12:00")
            )
            writer.writerow([
                match.matchday,
                kickoff.strftime("%d/%m/%Y") if kickoff else "Fecha por confirmar",
                "Tiempo pendiente de confirmar" if time_pending else kickoff.strftime("%H:%M"),
                match.home_team.name,
                match.away_team.name,
                match.score_display1 if match.is_played else "",
                "Pendiente de confirmar" if time_pending else "Confirmada",
            ])

    filename = f"jornadas_{season.name if season else 'liga'}.csv".replace(" ", "_")
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
