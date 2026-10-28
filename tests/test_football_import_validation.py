import unittest
from datetime import datetime

from scripts.football_import_validation import (
    Fixture,
    Matchday,
    normalize_team_name,
    validate_matchday,
)


class MatchdayValidationTests(unittest.TestCase):
    def setUp(self):
        self.teams = tuple(f"Team {i}" for i in range(1, 16))
        self.aliases = {normalize_team_name(name): name for name in self.teams}
        self.fixtures = tuple(
            Fixture(self.teams[i], self.teams[i + 1], 1)
            for i in range(0, 14, 2)
        )
        self.data = Matchday(
            competition="Juvenil Segona Divisió Grup 29",
            season="2026-2027",
            matchday=1,
            team_names=self.teams,
            fixtures=self.fixtures,
            resting_team=self.teams[14],
        )

    def test_complete_matchday_passes(self):
        self.assertEqual(validate_matchday(self.data, self.aliases), [])

    def test_incomplete_matchday_is_rejected(self):
        incomplete = Matchday(
            **{**self.data.__dict__, "fixtures": self.data.fixtures[:-1]}
        )
        self.assertIn("incomplete_matchday", validate_matchday(incomplete, self.aliases))

    def test_unknown_team_is_rejected(self):
        fixture = Fixture("Unlisted FC", self.teams[1], 1)
        invalid = Matchday(
            **{**self.data.__dict__, "fixtures": (fixture,) + self.data.fixtures[1:]}
        )
        errors = validate_matchday(invalid, self.aliases)
        self.assertTrue(any(error.startswith("unknown_fixture_team:") for error in errors))

    def test_non_final_score_is_rejected(self):
        fixtures = list(self.data.fixtures)
        fixtures[0] = Fixture(self.teams[0], self.teams[1], 1, home_goals=2, away_goals=0)
        invalid = Matchday(**{**self.data.__dict__, "fixtures": tuple(fixtures)})
        self.assertIn("score_not_confirmed_final", validate_matchday(invalid, self.aliases))

    def test_placeholder_midnight_is_rejected(self):
        fixtures = list(self.data.fixtures)
        fixtures[0] = Fixture(
            self.teams[0], self.teams[1], 1, kickoff=datetime(2026, 10, 31, 0, 0)
        )
        invalid = Matchday(**{**self.data.__dict__, "fixtures": tuple(fixtures)})
        self.assertIn(
            "midnight_kickoff_requires_confirmation",
            validate_matchday(invalid, self.aliases),
        )


if __name__ == "__main__":
    unittest.main()
