"""
Players routes - player profile.
"""

from flask import render_template, request
from app.blueprints.players import players_bp
from app.models import Player, Match, MatchEvent


@players_bp.route("/<int:player_id>")
def profile(player_id):
    """Player profile page with stats."""
    player = Player.query.get_or_404(player_id)

    # Recent match events (goals, assists)
    recent_events = (
        MatchEvent.query.join(Match)
        .filter(
            (MatchEvent.goal_scorer_id == player.id) | (MatchEvent.assist_id == player.id),
            MatchEvent.event_type == MatchEvent.TYPE_GOAL,
        )
        .order_by(Match.kickoff.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "players/profile.html",
        player=player,
        recent_events=recent_events,
    )
