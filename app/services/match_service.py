"""
Match service - records match results, updates stats, triggers standings.
Transaction-safe. No duplicated stat logic - single source of truth.
"""

from datetime import datetime
from app.extensions import db
from app.models import Match, MatchEvent, Player, Standing
from app.services.standings_service import StandingsService


class MatchService:
    """Service for recording match results and updating all derived stats."""

    @classmethod
    def record_match_result(
        cls,
        match_id: int,
        home_goals: int,
        away_goals: int,
        events: list | None = None,
    ) -> Match:
        """
        Record match result and update all stats.
        Transaction-safe: rolls back on any error.

        Args:
            match_id: Match to update
            home_goals: Home team goals
            away_goals: Away team goals
            events: List of dicts: {event_type, minute, player_id, ...}

        Returns:
            Updated Match instance

        Raises:
            ValueError: If match not found or invalid
        """
        match = Match.query.get_or_404(match_id)

        # If already recorded, we need to revert stats first, then re-apply
        if match.is_played:
            cls._revert_match_stats(match)

        try:
            match.home_goals = home_goals
            match.away_goals = away_goals
            match.is_played = True
            match.played_at = datetime.utcnow()

            # Clear existing events and add new ones
            MatchEvent.query.filter_by(match_id=match_id).delete()

            if events:
                for ev in events:
                    event = cls._create_match_event(match, ev)
                    if event:
                        db.session.add(event)

            db.session.flush()

            # Update team stats via standings (single source of truth)
            StandingsService.update_standings(match.season_id)

            # Update player stats from events
            cls._update_player_stats_from_events(match)

            db.session.commit()
            return match

        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def _revert_match_stats(cls, match: Match) -> None:
        """Revert player stats for a previously recorded match."""
        for event in match.events.all():
            player = Player.query.get(event.player_id)
            if not player:
                continue

            if event.event_type == MatchEvent.TYPE_GOAL:
                if event.goal_scorer_id:
                    scorer = Player.query.get(event.goal_scorer_id)
                    if scorer:
                        scorer.goals = max(0, scorer.goals - 1)
                if event.assist_id:
                    assister = Player.query.get(event.assist_id)
                    if assister:
                        assister.assists = max(0, assister.assists - 1)
            elif event.event_type == MatchEvent.TYPE_YELLOW:
                player.yellow_cards = max(0, player.yellow_cards - 1)
            elif event.event_type == MatchEvent.TYPE_RED:
                player.red_cards = max(0, player.red_cards - 1)

        # Revert appearances for players who participated
        home_ids = {e.player_id for e in match.events.all()}
        home_ids.update({e.goal_scorer_id for e in match.events.all() if e.goal_scorer_id})
        home_ids.update({e.assist_id for e in match.events.all() if e.assist_id})
        home_ids.update({e.player_off_id for e in match.events.all() if e.player_off_id})
        home_ids.update({e.player_on_id for e in match.events.all() if e.player_on_id})

        for pid in home_ids:
            p = Player.query.get(pid)
            if p:
                p.appearances = max(0, p.appearances - 1)

        # Clean sheets reverted via standings recalc - we'll recalc anyway

    @classmethod
    def _create_match_event(cls, match: Match, data: dict) -> MatchEvent | None:
        """Create MatchEvent from dict."""
        event_type = data.get("event_type")
        if not event_type:
            return None

        ev = MatchEvent(
            match_id=match.id,
            event_type=event_type,
            minute=data.get("minute", 0),
            extra_time=data.get("extra_time"),
            player_id=data.get("player_id"),
        )

        if event_type == MatchEvent.TYPE_GOAL:
            ev.goal_scorer_id = data.get("goal_scorer_id") or data.get("player_id")
            ev.player_id = ev.goal_scorer_id or data.get("player_id")
            ev.assist_id = data.get("assist_id")
            ev.is_penalty = data.get("is_penalty", False)
            ev.is_own_goal = data.get("is_own_goal", False)
        elif event_type in (MatchEvent.TYPE_YELLOW, MatchEvent.TYPE_RED):
            ev.player_id = data.get("player_id")
        elif event_type == MatchEvent.TYPE_SUBSTITUTION:
            ev.player_off_id = data.get("player_off_id")
            ev.player_on_id = data.get("player_on_id")
            ev.player_id = data.get("player_off_id") or data.get("player_on_id") or data.get("player_id")

        if not ev.player_id:
            return None
        return ev

    @classmethod
    def _update_player_stats_from_events(cls, match: Match) -> None:
        """Update player goals, assists, cards, appearances, clean sheets from events."""
        home_team_id = match.home_team_id
        away_team_id = match.away_team_id
        home_goals = match.home_goals or 0
        away_goals = match.away_goals or 0

        participants = set()

        for event in match.events:
            # Appearances: any player in an event
            for attr in ("player_id", "goal_scorer_id", "assist_id", "player_off_id", "player_on_id"):
                pid = getattr(event, attr, None)
                if pid:
                    participants.add(pid)

            if event.event_type == MatchEvent.TYPE_GOAL:
                scorer_id = event.goal_scorer_id or event.player_id
                if scorer_id and not event.is_own_goal:
                    scorer = Player.query.get(scorer_id)
                    if scorer:
                        scorer.goals = (scorer.goals or 0) + 1
                if event.assist_id:
                    assister = Player.query.get(event.assist_id)
                    if assister:
                        assister.assists = (assister.assists or 0) + 1
            elif event.event_type == MatchEvent.TYPE_YELLOW:
                p = Player.query.get(event.player_id)
                if p:
                    p.yellow_cards = (p.yellow_cards or 0) + 1
            elif event.event_type == MatchEvent.TYPE_RED:
                p = Player.query.get(event.player_id)
                if p:
                    p.red_cards = (p.red_cards or 0) + 1

        for pid in participants:
            p = Player.query.get(pid)
            if p:
                p.appearances = (p.appearances or 0) + 1

        # Clean sheets: GK/DEF who played (in events) and team conceded 0
        home_conceded = away_goals
        away_conceded = home_goals

        home_def_players = set()
        away_def_players = set()
        
        # Get all players who participated in the match
        for e in match.events:
            # Check all possible player relationships for participation
            for attr in ("player_id", "goal_scorer_id", "assist_id", "player_off_id", "player_on_id"):
                pid = getattr(e, attr, None)
                if pid:
                    p = Player.query.get(pid)
                    if p and p.is_goalkeeper_or_defender():
                        if p.team_id == home_team_id:
                            home_def_players.add(pid)
                        elif p.team_id == away_team_id:
                            away_def_players.add(pid)

        # Award clean sheets
        if home_conceded == 0:
            for pid in home_def_players:
                p = Player.query.get(pid)
                if p:
                    p.clean_sheets = (p.clean_sheets or 0) + 1
        if away_conceded == 0:
            for pid in away_def_players:
                p = Player.query.get(pid)
                if p:
                    p.clean_sheets = (p.clean_sheets or 0) + 1
