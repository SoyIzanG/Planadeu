"""
Teams routes - team profile, squad, stats and upcoming fixtures.
"""

from datetime import datetime

from flask import render_template, abort, redirect, url_for
from app.blueprints.teams import teams_bp
from app.models import Team, Standing, Match, Season


@teams_bp.route("/<string:team_identifier>")
def profile(team_identifier):
    """Team profile page, reachable by readable team slug."""
    if team_identifier.isdigit():
        team = Team.query.get_or_404(int(team_identifier))
        return redirect(url_for("teams.profile", team_identifier=team.slug), code=301)

    team = next(
        (candidate for candidate in Team.query.all() if candidate.slug == team_identifier),
        None,
    )
    if team is None:
        abort(404)

    season = Season.query.filter_by(is_active=True).first()
    if not season:
        season = Season.query.order_by(Season.start_date.desc()).first()

    standing = None
    if season and team in season.teams:
        standing = Standing.query.filter_by(season_id=season.id, team_id=team.id).first()

    matches = (
        Match.query.filter(
            (Match.home_team_id == team.id) | (Match.away_team_id == team.id),
            Match.is_played.is_(True),
        )
        .order_by(Match.kickoff.desc())
        .limit(5)
        .all()
    )

    form = []
    for match in matches:
        if match.home_team_id == team.id:
            if match.home_goals > match.away_goals:
                form.append("W")
            elif match.home_goals < match.away_goals:
                form.append("L")
            else:
                form.append("D")
        else:
            if match.away_goals > match.home_goals:
                form.append("W")
            elif match.away_goals < match.home_goals:
                form.append("L")
            else:
                form.append("D")

    upcoming_matches = []
    if season:
        upcoming_matches = (
            Match.query.filter(
                Match.season_id == season.id,
                (Match.home_team_id == team.id) | (Match.away_team_id == team.id),
                Match.is_played.is_(False),
                Match.kickoff >= datetime.now(),
            )
            .order_by(Match.kickoff.asc(), Match.matchday.asc())
            .all()
        )

    return render_template(
        "teams/profile.html",
        team=team,
        season=season,
        standing=standing,
        form="".join(form),
        recent_matches=matches,
        upcoming_matches=upcoming_matches,
    )
