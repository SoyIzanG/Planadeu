"""
Standings service - calculates and updates league table.
Ranking: 1) Points 2) Goal difference 3) Goals scored 4) Head-to-head
"""

from collections import defaultdict
from app.extensions import db
from app.models import Season, Team, Match, Standing


class StandingsService:
    """Service for calculating and updating league standings."""

    POINTS_WIN = 3
    POINTS_DRAW = 1
    POINTS_LOSS = 0

    @classmethod
    def update_standings(cls, season_id: int) -> None:
        """
        Recalculate standings for a season.
        Transaction-safe: all updates in single transaction.
        
        Args:
            season_id: Season to update standings for
        """
        season = Season.query.get_or_404(season_id)
        
        # Get teams in this season
        team_ids = [t.id for t in season.teams]
        if not team_ids:
            return

        # Initialize stats per team
        stats = {
            tid: {
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "goals_for": 0,
                "goals_against": 0,
                "matches": [],  # (opponent_id, pts, gf, ga) for head-to-head
            }
            for tid in team_ids
        }

        # Process played matches
        matches = Match.query.filter_by(
            season_id=season_id,
            is_played=True,
        ).filter(
            Match.home_goals.isnot(None),
            Match.away_goals.isnot(None),
        ).all()

        for match in matches:
            if match.home_team_id not in team_ids or match.away_team_id not in team_ids:
                continue

            hg, ag = match.home_goals, match.away_goals
            stats[match.home_team_id]["played"] += 1
            stats[match.away_team_id]["played"] += 1
            stats[match.home_team_id]["goals_for"] += hg
            stats[match.home_team_id]["goals_against"] += ag
            stats[match.away_team_id]["goals_for"] += ag
            stats[match.away_team_id]["goals_against"] += hg

            if hg > ag:
                stats[match.home_team_id]["won"] += 1
                stats[match.away_team_id]["lost"] += 1
                stats[match.home_team_id]["matches"].append((match.away_team_id, 3, hg, ag))
                stats[match.away_team_id]["matches"].append((match.home_team_id, 0, ag, hg))
            elif ag > hg:
                stats[match.away_team_id]["won"] += 1
                stats[match.home_team_id]["lost"] += 1
                stats[match.away_team_id]["matches"].append((match.home_team_id, 3, ag, hg))
                stats[match.home_team_id]["matches"].append((match.away_team_id, 0, hg, ag))
            else:
                stats[match.home_team_id]["drawn"] += 1
                stats[match.away_team_id]["drawn"] += 1
                stats[match.home_team_id]["matches"].append((match.away_team_id, 1, hg, ag))
                stats[match.away_team_id]["matches"].append((match.home_team_id, 1, ag, hg))

        # Build form (last 5 matches) per team
        form_map = cls._build_form_map(season_id, team_ids)

        # Compute points, goal diff
        for tid in team_ids:
            s = stats[tid]
            s["points"] = s["won"] * cls.POINTS_WIN + s["drawn"] * cls.POINTS_DRAW
            s["goal_difference"] = s["goals_for"] - s["goals_against"]
            s["form"] = form_map.get(tid, "")

        # Sort: points, GD, GF, then head-to-head
        sorted_teams = cls._rank_teams(team_ids, stats)

        # Get existing standings for previous_position
        existing = {
            s.team_id: s.position
            for s in Standing.query.filter_by(season_id=season_id).all()
        }

        # Delete old standings and insert new (in transaction)
        Standing.query.filter_by(season_id=season_id).delete()

        for pos, team_id in enumerate(sorted_teams, start=1):
            s = stats[team_id]
            prev = existing.get(team_id)
            standing = Standing(
                season_id=season_id,
                team_id=team_id,
                position=pos,
                previous_position=prev,
                played=s["played"],
                won=s["won"],
                drawn=s["drawn"],
                lost=s["lost"],
                goals_for=s["goals_for"],
                goals_against=s["goals_against"],
                goal_difference=s["goal_difference"],
                points=s["points"],
                form=s["form"],
            )
            db.session.add(standing)

        db.session.commit()

    @classmethod
    def _build_form_map(cls, season_id: int, team_ids: list) -> dict:
        """Build form string (W/D/L) for last 5 matches per team."""
        matches = (
            Match.query.filter_by(season_id=season_id, is_played=True)
            .filter(Match.home_goals.isnot(None), Match.away_goals.isnot(None))
            .order_by(Match.kickoff.desc())
            .all()
        )

        # Per team: list of "W"/"D"/"L" from most recent
        form_lists = defaultdict(list)

        for m in matches:
            if m.home_team_id not in team_ids and m.away_team_id not in team_ids:
                continue

            hg, ag = m.home_goals, m.away_goals
            if m.home_team_id in team_ids:
                if len(form_lists[m.home_team_id]) < 5:
                    if hg > ag:
                        form_lists[m.home_team_id].append("W")
                    elif hg < ag:
                        form_lists[m.home_team_id].append("L")
                    else:
                        form_lists[m.home_team_id].append("D")
            if m.away_team_id in team_ids:
                if len(form_lists[m.away_team_id]) < 5:
                    if ag > hg:
                        form_lists[m.away_team_id].append("W")
                    elif ag < hg:
                        form_lists[m.away_team_id].append("L")
                    else:
                        form_lists[m.away_team_id].append("D")

        return {tid: "".join(form_lists[tid]) for tid in team_ids}

    @classmethod
    def _rank_teams(cls, team_ids: list, stats: dict) -> list:
        """
        Rank teams by: 1) Points 2) GD 3) GF 4) Head-to-head.
        Returns ordered list of team_ids.
        """
        def key(tid):
            s = stats[tid]
            return (-s["points"], -s["goal_difference"], -s["goals_for"], tid)

        # Primary sort
        ordered = sorted(team_ids, key=key)

        # Resolve ties with head-to-head
        result = []
        i = 0
        while i < len(ordered):
            # Find group with same (pts, gd, gf)
            group = [ordered[i]]
            k0 = key(ordered[i])
            j = i + 1
            while j < len(ordered) and key(ordered[j])[:3] == k0[:3]:
                group.append(ordered[j])
                j += 1

            if len(group) == 1:
                result.append(group[0])
            else:
                # Head-to-head among group
                subgroup = cls._head_to_head_rank(group, stats)
                result.extend(subgroup)

            i = j

        return result

    @classmethod
    def _head_to_head_rank(cls, team_ids: list, stats: dict) -> list:
        """Rank teams by head-to-head results among the group."""
        group_set = set(team_ids)
        h2h = {tid: {"pts": 0, "gd": 0, "gf": 0} for tid in team_ids}

        for tid in team_ids:
            for opp_id, pts, gf, ga in stats[tid]["matches"]:
                if opp_id in group_set:
                    h2h[tid]["pts"] += pts
                    h2h[tid]["gd"] += gf - ga
                    h2h[tid]["gf"] += gf

        def h2h_key(tid):
            h = h2h[tid]
            return (-h["pts"], -h["gd"], -h["gf"], tid)

        return sorted(team_ids, key=h2h_key)
