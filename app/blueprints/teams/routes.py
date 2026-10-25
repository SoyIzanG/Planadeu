"""
Teams routes - team profile, squad, stats.
"""

from flask import render_template, abort
from app.blueprints.teams import teams_bp
from app.models import Team, Standing, Match, Season


@teams_bp.route("/<int:team_id>")
def profile(team_id):
    """Team profile page with squad and stats."""
    team = Team.query.get_or_404(team_id)
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        season = Season.query.order_by(Season.start_date.desc()).first()

    standing = None
    if season and team in season.teams:
        standing = Standing.query.filter_by(
            season_id=season.id,
            team_id=team.id,
        ).first()

    # Last 5 matches (form)
    matches = (
        Match.query.filter(
            (Match.home_team_id == team.id) | (Match.away_team_id == team.id),
            Match.is_played == True,
        )
        .order_by(Match.kickoff.desc())
        .limit(5)
        .all()
    )

    form = []
    for m in matches:
        if m.home_team_id == team.id:
            if m.home_goals > m.away_goals:
                form.append("W")
            elif m.home_goals < m.away_goals:
                form.append("L")
            else:
                form.append("D")
        else:
            if m.away_goals > m.home_goals:
                form.append("W")
            elif m.away_goals < m.home_goals:
                form.append("L")
            else:
                form.append("D")
    form_str = "".join(form)

    return render_template(
        "teams/profile.html",
        team=team,
        season=season,
        standing=standing,
        form=form_str,
        recent_matches=matches,
    )
