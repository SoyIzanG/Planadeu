import contextlib
import io
import json
import unittest
from unittest.mock import patch

import scripts.fcf_sync as fcf_sync
import scripts.sync_futbuteo as sync_futbuteo

from scripts.fcf_sync import (
    extract_result_rows,
    result_matchday,
    summarize_results,
    normalize_modern_fixture_rows,
)


def row(home, away, day=1, **extra):
    return {
        "jornada_numero": day,
        "equipo_local_nombre": home,
        "equipo_visitante_nombre": away,
        "fecha_partido": "2026-10-31",
        "hora_partido": "12:00:00",
        "acta_cerrada": False,
        "resultado_provisional": True,
        **extra,
    }


class FcfApiAdapterTests(unittest.TestCase):
    def test_extracts_legacy_root_array(self):
        rows = extract_result_rows([row("A", "B")])
        self.assertEqual(len(rows), 1)

    def test_extracts_results_envelope(self):
        rows = extract_result_rows({"resultados": [row("A", "B")]})
        self.assertEqual(rows[0]["equipo_local_nombre"], "A")

    def test_rejects_unrecognized_payload(self):
        with self.assertRaisesRegex(ValueError, "no results array"):
            extract_result_rows({"error": "not found"})

    def test_matchday_is_normalized(self):
        self.assertEqual(result_matchday(row("A", "B", "5")), 5)
        self.assertIsNone(result_matchday({"jornada_numero": "unknown"}))

    def test_normalizes_modern_fcf_fixture_fields(self):
        rows = normalize_modern_fixture_rows({
            "data": [{
                "jornada": 5,
                "equipLocal": {"nom": "Planadeu C"},
                "equipVisitant": {"nom": "Can Trias B"},
                "data": "2026-10-31",
                "hora": "12:00",
                "golsLocal": 2,
                "golsVisitant": 1,
            }]
        })
        self.assertEqual(rows[0]["equipo_local_nombre"], "Planadeu C")
        self.assertEqual(rows[0]["equipo_visitante_nombre"], "Can Trias B")
        self.assertEqual(rows[0]["equipo_local_goles"], 2)

    def test_rejects_unknown_modern_fixture_schema(self):
        with self.assertRaisesRegex(ValueError, "schema is not recognized"):
            normalize_modern_fixture_rows([{"id": 123, "foo": "bar"}])

    def test_complete_matchday_shape_passes(self):
        teams = [f"Team {i}" for i in range(1, 16)] + ["Planadeu C"]
        fixtures = [row(teams[i], teams[i + 1], 5) for i in range(0, 16, 2)]
        summary = summarize_results(fixtures, 5)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["fixture_count"], 8)
        self.assertEqual(summary["distinct_team_count"], 16)

    def test_incomplete_matchday_fails(self):
        summary = summarize_results([row("A", "B", 5)], 5)
        self.assertFalse(summary["ok"])
        self.assertIn("expected_8_fixtures_got_1", summary["validation_errors"])

    def test_does_not_mark_provisional_score_as_final(self):
        fixture = row("A", "B", 5, equipo_local_goles=2, equipo_visitante_goles=1)
        summary = summarize_results([fixture], None)
        self.assertEqual(summary["fixtures"][0]["acta_closed"], False)
        self.assertEqual(summary["fixtures"][0]["provisional"], True)


class DailySyncParserTests(unittest.TestCase):
    def setUp(self):
        self.teams = [f"Team {i}" for i in range(1, 16)] + ["UE Planadeu"]

    def fixture_html(self, count=8, include_planadeu=True, final=False):
        teams = list(self.teams)
        if not include_planadeu:
            teams = [team for team in teams if team != "UE Planadeu"]
        cards = []
        pairs = list(zip(teams[::2], teams[1::2]))
        if not include_planadeu:
            pairs = pairs[:7]
        else:
            pairs = pairs[:count]
        for i, (home, away) in enumerate(pairs):
            score = " 2 - 1 FT" if final else " 2 - 1"
            cards.append(
                '<div class="fixture">'
                f'{home} vs {away} '
                f'<time datetime="2026-10-{31-i:02d}T12:00"></time> '
                '12:00'
                f'{score}</div>'
            )
        return (
            "<html><body><h1>Juvenil Segona Divisió Grup 29</h1>"
            "<p>Temporada 2026-2027</p>"
            + "".join(cards)
            + "</body></html>"
        )

    def test_hidden_script_schedule_does_not_count_as_rendered_page(self):
        html = (
            "<html><body><p>Loading…</p>"
            "<script>sessionStorage.setItem('x','1'); "
            "Juvenil Segona Divisio Grup 29 Team 1 Team 2</script>"
            "</body></html>"
        )
        self.assertTrue(sync_futbuteo._looks_like_challenge(html))

    def test_rendered_group_page_is_not_classified_as_js_shell(self):
        html = (
            "<html><body><h1>Juvenil Segona Divisió Grup 29</h1>"
            + " ".join(f"Team {i}" for i in range(1, 17))
            + " Temporada 2026-2027 Jornada 1 calendari resultats "
            + ("partit equip futbol " * 15)
            + "<script>sessionStorage.setItem('x','1')</script></body></html>"
        )
        self.assertFalse(sync_futbuteo._looks_like_challenge(html))

    def test_missing_planadeu_slot_is_reconstructed_only_from_named_bye(self):
        teams = [f"Team {i}" for i in range(1, 16)] + ["UE Planadeu"]
        source_html = self.fixture_html(include_planadeu=False).replace(
            "<h2>Jornada 1</h2>",
            "<h2>Jornada 1</h2><p>Descans: Team 15</p>",
        )
        parsed, error = sync_futbuteo.parse_round(source_html, teams, 1, "test")
        self.assertIsNone(error)
        self.assertEqual(len(parsed["fixtures"]), 8)
        self.assertTrue(parsed["inferred_planadeu_fixture"])
        inferred = [f for f in parsed["fixtures"] if not f["kickoff_confirmed"]]
        self.assertEqual(len(inferred), 1)
        self.assertIn("UE Planadeu", {inferred[0]["home"], inferred[0]["away"]})
        self.assertIn("Team 15", {inferred[0]["home"], inferred[0]["away"]})
        self.assertIsNone(inferred[0]["home_goals"])
        self.assertIsNone(inferred[0]["away_goals"])

    def test_bye_reconstruction_is_rejected_when_the_named_resting_team_differs(self):
        teams = [f"Team {i}" for i in range(1, 16)] + ["UE Planadeu"]
        source_html = self.fixture_html(include_planadeu=False).replace(
            "<h2>Jornada 1</h2>",
            "<h2>Jornada 1</h2><p>Descans: Team 13</p>",
        )
        parsed, error = sync_futbuteo.parse_round(source_html, teams, 1, "test")
        self.assertIsNone(parsed)
        self.assertIsNotNone(error)

    def test_target_round_requires_all_16_teams_and_eight_fixtures(self):
        parsed, error = sync_futbuteo.parse_round(
            self.fixture_html(), self.teams, 1, "test"
        )
        self.assertIsNone(error)
        self.assertEqual(len(parsed["fixtures"]), 8)
        self.assertIn("UE Planadeu", [t for item in parsed["fixtures"] for t in (item["home"], item["away"])])

    def test_futbuteo_source_round_index_starts_at_five(self):
        self.assertEqual(sync_futbuteo.futbuteo_query_for_matchday(1), 5)
        self.assertEqual(sync_futbuteo.futbuteo_query_for_matchday(5), 9)
        self.assertEqual(sync_futbuteo.futbuteo_query_for_matchday(30), 34)

    def test_visible_round_heading_is_used_to_select_round(self):
        html = self.fixture_html().replace(
            "<p>Temporada 2026-2027</p>",
            "<h2>Jornada 1</h2><p>Temporada 2026-2027</p>",
        )
        parsed, error = sync_futbuteo.parse_round(html, self.teams, 1, "test")
        self.assertIsNone(error)
        self.assertEqual(len(parsed["fixtures"]), 8)
        wrong_round, wrong_error = sync_futbuteo.parse_round(html, self.teams, 2, "test")
        self.assertIsNone(wrong_round)
        self.assertIsNotNone(wrong_error)

    def test_15_team_public_schedule_is_rejected(self):
        parsed, error = sync_futbuteo.parse_round(
            self.fixture_html(include_planadeu=False), self.teams, 1, "test"
        )
        self.assertIsNone(parsed)
        self.assertIn("se exigen 8", error)
        self.assertIn("Planadeu=ausente", error)

    def club_feed(self, **overrides):
        teams = [f"Team {i}" for i in range(1, 16)] + ["UE Planadeu"]
        payload = {
            "competition": "Juvenil Segona Divisió Grup 29",
            "season": "2026-2027",
            "teams": teams,
            "fixtures": [
                {
                    "matchday": 1,
                    "home": teams[i],
                    "away": teams[i + 1],
                    "date": "2026-10-31",
                    "time": "12:00",
                }
                for i in range(0, 16, 2)
            ],
        }
        payload.update(overrides)
        return payload

    def test_approved_club_feed_is_accepted(self):
        teams = [f"Team {i}" for i in range(1, 16)] + ["UE Planadeu"]
        parsed, error = sync_futbuteo.parse_club_feed(self.club_feed(), teams, 1)
        self.assertIsNone(error)
        self.assertEqual(len(parsed["fixtures"]), 8)
        self.assertEqual(parsed["source"], "Club feed")
        self.assertTrue(all(item["kickoff_confirmed"] for item in parsed["fixtures"]))

    def test_club_feed_rejects_wrong_competition(self):
        teams = [f"Team {i}" for i in range(1, 16)] + ["UE Planadeu"]
        parsed, error = sync_futbuteo.parse_club_feed(
            self.club_feed(competition="Juvenil Segona Divisió Grup 28"),
            teams,
            1,
        )
        self.assertIsNone(parsed)
        self.assertIn("Grup 29", error)

    def test_club_feed_rejects_incomplete_round(self):
        teams = [f"Team {i}" for i in range(1, 16)] + ["UE Planadeu"]
        feed = self.club_feed()
        feed["fixtures"] = feed["fixtures"][:-1]
        parsed, error = sync_futbuteo.parse_club_feed(feed, teams, 1)
        self.assertIsNone(parsed)
        self.assertIn("se exigen 8", error)

    def test_club_feed_does_not_import_unfinalized_scores(self):
        teams = [f"Team {i}" for i in range(1, 16)] + ["UE Planadeu"]
        feed = self.club_feed()
        feed["fixtures"][0].update({"home_goals": 3, "away_goals": 1, "result_is_final": False})
        parsed, error = sync_futbuteo.parse_club_feed(feed, teams, 1)
        self.assertIsNone(error)
        self.assertIsNone(parsed["fixtures"][0]["home_goals"])
        self.assertIsNone(parsed["fixtures"][0]["away_goals"])

    def test_kickoff_clock_is_not_misread_as_score(self):
        parsed, error = sync_futbuteo.parse_round(
            self.fixture_html(final=False), self.teams, 1, "test"
        )
        self.assertIsNone(error)
        self.assertTrue(all(item["home_goals"] is None for item in parsed["fixtures"]))
        self.assertTrue(all(item["away_goals"] is None for item in parsed["fixtures"]))

    def test_only_explicitly_final_scores_are_imported(self):
        parsed, error = sync_futbuteo.parse_round(
            self.fixture_html(final=True), self.teams, 1, "test"
        )
        self.assertIsNone(error)
        self.assertTrue(all(item["result_is_final"] for item in parsed["fixtures"]))
        self.assertEqual(parsed["fixtures"][0]["home_goals"], 2)
        self.assertEqual(parsed["fixtures"][0]["away_goals"], 1)


if __name__ == "__main__":
    unittest.main()
