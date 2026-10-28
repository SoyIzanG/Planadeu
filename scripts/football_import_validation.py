"""Validation primitives for importing official football matchdays.

This module intentionally has no database dependency. Source adapters must turn
FCF/Futbuteo pages into normalized records first; only a complete, unambiguous
matchday may pass validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata


EXPECTED_TEAM_COUNT = 16
EXPECTED_FIXTURES_PER_MATCHDAY = 8


def normalize_team_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


@dataclass(frozen=True)
class Fixture:
    home: str
    away: str
    matchday: int
    kickoff: datetime | None = None
    kickoff_confirmed: bool = False
    home_goals: int | None = None
    away_goals: int | None = None
    result_is_final: bool = False


@dataclass(frozen=True)
class Matchday:
    competition: str
    season: str
    matchday: int
    team_names: tuple[str, ...]
    fixtures: tuple[Fixture, ...]
    resting_team: str | None = None


def validate_matchday(data: Matchday, aliases: dict[str, str]) -> list[str]:
    """Return validation errors; an empty list means structurally safe to stage."""
    errors: list[str] = []
    if normalize_team_name(data.competition) != normalize_team_name(
        "Juvenil Segona Divisió Grup 29"
    ):
        errors.append("competition_mismatch")
    if not re.fullmatch(r"20\d{2}-20\d{2}", data.season):
        errors.append("invalid_season")
    if data.matchday < 1 or data.matchday > 30:
        errors.append("invalid_matchday")
    if len(data.team_names) != EXPECTED_TEAM_COUNT:
        errors.append("unexpected_team_count")
    canonical_teams: list[str] = []
    for name in data.team_names:
        canonical = aliases.get(normalize_team_name(name))
        if not canonical:
            errors.append(f"unknown_team:{name}")
        else:
            canonical_teams.append(canonical)
    if len(set(canonical_teams)) != len(canonical_teams):
        errors.append("duplicate_team_identity")
    if len(set(canonical_teams)) != EXPECTED_TEAM_COUNT:
        errors.append("incomplete_team_roster")
    if len(data.fixtures) != EXPECTED_FIXTURES_PER_MATCHDAY:
        errors.append("incomplete_matchday")
    used: list[str] = []
    for fixture in data.fixtures:
        if fixture.matchday != data.matchday:
            errors.append("fixture_matchday_mismatch")
        home = aliases.get(normalize_team_name(fixture.home))
        away = aliases.get(normalize_team_name(fixture.away))
        if not home or not away:
            errors.append(f"unknown_fixture_team:{fixture.home}:{fixture.away}")
            continue
        if home == away:
            errors.append("team_playing_itself")
        used.extend([home, away])
        if (fixture.home_goals is None) != (fixture.away_goals is None):
            errors.append("partial_score")
        if fixture.home_goals is not None:
            if fixture.home_goals < 0 or fixture.away_goals is None or fixture.away_goals < 0:
                errors.append("invalid_score")
            if not fixture.result_is_final:
                errors.append("score_not_confirmed_final")
        if fixture.kickoff is not None and not fixture.kickoff_confirmed:
            errors.append("kickoff_not_confirmed")
        if fixture.kickoff is not None and fixture.kickoff.time().isoformat() == "00:00:00" and not fixture.kickoff_confirmed:
            # Midnight may be legitimate, but placeholder midnight must never be
            # imported without explicit confirmation from the source.
            errors.append("midnight_kickoff_requires_confirmation")
    if len(set(used)) != len(used):
        errors.append("team_appears_more_than_once")
    if set(used) != set(canonical_teams):
        errors.append("team_fixture_coverage_mismatch")
    if data.resting_team:
        resting = aliases.get(normalize_team_name(data.resting_team))
        if not resting:
            errors.append(f"unknown_resting_team:{data.resting_team}")
        else:
            errors.append("unexpected_resting_team_in_16_team_competition")
    return sorted(set(errors))
