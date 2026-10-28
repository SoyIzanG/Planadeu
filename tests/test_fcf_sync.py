import contextlib
import io
import json
import unittest
from unittest.mock import patch

import scripts.fcf_sync as fcf_sync

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
        teams = [f"Team {i}" for i in range(1, 15)]
        fixtures = [row(teams[i], teams[i + 1], 5) for i in range(0, 14, 2)]
        summary = summarize_results(fixtures, 5)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["fixture_count"], 7)
        self.assertEqual(summary["distinct_team_count"], 14)

    def test_incomplete_matchday_fails(self):
        summary = summarize_results([row("A", "B", 5)], 5)
        self.assertFalse(summary["ok"])
        self.assertIn("expected_7_fixtures_got_1", summary["validation_errors"])

    def test_does_not_mark_provisional_score_as_final(self):
        fixture = row("A", "B", 5, equipo_local_goles=2, equipo_visitante_goles=1)
        summary = summarize_results([fixture], None)
        self.assertEqual(summary["fixtures"][0]["acta_closed"], False)
        self.assertEqual(summary["fixtures"][0]["provisional"], True)


if __name__ == "__main__":
    unittest.main()
