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
            .filter(Match.matchday > 0)
            .filter((Match.kickoff.is_(None)) | (Match.kickoff >= datetime(2026, 10, 31)))
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
    """Download the season fixtures as a PDF."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    season = _active_season()
    matches = []
    if season:
        matches = (
            Match.query.filter_by(season_id=season.id)
            .filter(Match.matchday > 0)
            .filter((Match.kickoff.is_(None)) | (Match.kickoff >= datetime(2026, 10, 31)))
            .order_by(Match.matchday.asc(), Match.kickoff.asc(), Match.id.asc())
            .all()
        )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=12 * mm, leftMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    story = [Paragraph("Calendario de jornadas", styles["Title"])]
    if season:
        story.append(Paragraph(season.name, styles["Heading2"]))
    story.append(Spacer(1, 5 * mm))

    rows = [["Jornada", "Fecha", "Hora", "Local", "Visitante", "Resultado"]]
    for match in matches:
        kickoff = match.kickoff
        time_pending = (
            match.home_team.name == "UE Planadeu"
            or match.away_team.name == "UE Planadeu"
            or not match.kickoff_confirmed
            or (kickoff and kickoff.strftime("%H:%M") == "12:00")
        )
        rows.append([
            str(match.matchday),
            kickoff.strftime("%d/%m/%Y") if kickoff else "Por confirmar",
            "Pendiente de confirmar" if time_pending else kickoff.strftime("%H:%M"),
            match.home_team.name,
            match.away_team.name,
            match.score_display1 if match.is_played else "—",
        ])

    table = Table(rows, repeatRows=1, colWidths=[22*mm, 28*mm, 38*mm, 54*mm, 54*mm, 30*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E1F2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    doc.build(story)
    filename = f"jornadas_{season.name if season else 'liga'}.pdf".replace(" ", "_")
    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
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
