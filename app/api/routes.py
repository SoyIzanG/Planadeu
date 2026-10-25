"""
REST API routes - JSON responses for /api/table, /api/teams, etc.
"""

from flask import jsonify, request

from app.api import api_bp
from app.models import Season, Standing, Team, Player, Match


def _get_current_season():
    """Get active or latest season."""
    s = Season.query.filter_by(is_active=True).first()
    if not s:
        s = Season.query.order_by(Season.start_date.desc()).first()
    return s


@api_bp.route("/table")
def table():
    """GET /api/table - League standings as JSON."""
    season = _get_current_season()
    if not season:
        return jsonify({"season": None, "standings": []})

    standings = Standing.query.filter_by(season_id=season.id).order_by(Standing.position).all()
    data = {
        "season": season.name,
        "season_id": season.id,
        "standings": [
            {
                "position": s.position,
                "previous_position": s.previous_position,
                "position_change": s.position_change,
                "team_id": s.team_id,
                "team_name": s.team.name,
                "team_short_name": s.team.short_name,
                "played": s.played,
                "won": s.won,
                "drawn": s.drawn,
                "lost": s.lost,
                "goals_for": s.goals_for,
                "goals_against": s.goals_against,
                "goal_difference": s.goal_difference,
                "points": s.points,
                "form": s.form or "",
            }
            for s in standings
        ],
    }
    return jsonify(data)


@api_bp.route("/teams")
def teams():
    """GET /api/teams - Teams list with optional search and pagination."""
    q = Team.query
    search = request.args.get("q", "").strip()
    if search:
        q = q.filter(
            Team.name.ilike(f"%{search}%") | Team.short_name.ilike(f"%{search}%")
        )
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    pagination = q.order_by(Team.name).paginate(page=page, per_page=per_page, error_out=False)

    data = {
        "teams": [
            {
                "id": t.id,
                "name": t.name,
                "short_name": t.short_name,
                "logo": t.logo_filename,
                "founded_year": t.founded_year,
                "stadium": t.stadium,
            }
            for t in pagination.items
        ],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    }
    return jsonify(data)


@api_bp.route("/players")
def players():
    """GET /api/players - Players list with search and pagination."""
    q = Player.query.join(Team)
    search = request.args.get("q", "").strip()
    team_id = request.args.get("team_id", type=int)
    if search:
        q = q.filter(
            Player.first_name.ilike(f"%{search}%")
            | Player.last_name.ilike(f"%{search}%")
        )
    if team_id:
        q = q.filter(Player.team_id == team_id)

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    pagination = q.order_by(Player.last_name).paginate(page=page, per_page=per_page, error_out=False)

    data = {
        "players": [
            {
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "full_name": p.full_name,
                "team_id": p.team_id,
                "team_name": p.team.name,
                "position": p.position,
                "jersey_number": p.jersey_number,
                "age": p.age,
                "goals": p.goals,
                "assists": p.assists,
                "appearances": p.appearances,
            }
            for p in pagination.items
        ],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    }
    return jsonify(data)


@api_bp.route("/matches")
def matches():
    """GET /api/matches - Matches list by season and matchday."""
    season = _get_current_season()
    if not season:
        return jsonify({"season": None, "matches": []})

    q = Match.query.filter_by(season_id=season.id).order_by(Match.matchday, Match.kickoff)
    matchday = request.args.get("matchday", type=int)
    if matchday:
        q = q.filter_by(matchday=matchday)

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    data = {
        "season": season.name,
        "matches": [
            {
                "id": m.id,
                "matchday": m.matchday,
                "kickoff": m.kickoff.isoformat() if m.kickoff else None,
                "home_team_id": m.home_team_id,
                "home_team_name": m.home_team.name,
                "away_team_id": m.away_team_id,
                "away_team_name": m.away_team.name,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "is_played": m.is_played,
                "score_display": m.score_display,
            }
            for m in pagination.items
        ],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    }
    return jsonify(data)
