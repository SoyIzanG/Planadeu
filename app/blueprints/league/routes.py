"""
League routes - table, statistics, season selector.
"""

from datetime import date
from flask import render_template, request
from sqlalchemy import desc

from app.blueprints.league import league_bp
from app.models import Season, Standing, Team, Player, Match


@league_bp.route("/table")
def table():
    """League table page."""
    season = _get_current_season()
    standings = []
    if season:
        standings = (
            Standing.query.filter_by(season_id=season.id)
            .order_by(Standing.position)
            .all()
        )
    return render_template(
        "league/table.html",
        season=season,
        standings=standings,
    )


@league_bp.route("/statistics")
def statistics():
    """Statistics page - top scorers, assists, etc."""
    season = _get_current_season()
    team_ids = [t.id for t in season.teams] if season else []

    top_scorers = []
    top_assists = []
    clean_sheets = []
    most_cards = []

    if team_ids:
        top_scorers = (
            Player.query.filter(Player.team_id.in_(team_ids), Player.goals > 0)
            .order_by(desc(Player.goals), desc(Player.assists))
            .limit(10)
            .all()
        )
        top_assists = (
            Player.query.filter(Player.team_id.in_(team_ids), Player.assists > 0)
            .order_by(desc(Player.assists), desc(Player.goals))
            .limit(10)
            .all()
        )
        clean_sheets = (
            Player.query.filter(
                Player.team_id.in_(team_ids),
                Player.position.in_([Player.POSITION_GOALKEEPER, Player.POSITION_DEFENDER]),
                Player.clean_sheets > 0,
            )
            .order_by(desc(Player.clean_sheets))
            .limit(10)
            .all()
        )
        most_cards = (
            Player.query.filter(Player.team_id.in_(team_ids))
            .filter((Player.yellow_cards + Player.red_cards * 2) > 0)
            .order_by(desc(Player.yellow_cards + Player.red_cards * 2))
            .limit(10)
            .all()
        )

    return render_template(
        "league/statistics.html",
        season=season,
        top_scorers=top_scorers,
        top_assists=top_assists,
        clean_sheets=clean_sheets,
        most_cards=most_cards,
    )


def _get_current_season():
    """Get active season or latest one."""
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        season = Season.query.order_by(Season.start_date.desc()).first()
    return season
