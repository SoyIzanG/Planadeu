import unittest
from unittest.mock import patch

from scripts.fcf_sync import EXPECTED_MARKERS, inspect_source


class SourcePreflightTests(unittest.TestCase):
    @patch("scripts.fcf_sync.fetch_text", return_value=(200, "Juvenil Segona Divisio Grup 29 Jornada 5"))
    def test_valid_competition_page_passes(self, _fetch):
        result = inspect_source("test", "https://example.invalid")
        self.assertTrue(result["ok"])
        self.assertEqual(result["missing_markers"], [])

    @patch("scripts.fcf_sync.fetch_text", return_value=(200, "Different competition"))
    def test_wrong_competition_fails(self, _fetch):
        result = inspect_source("test", "https://example.invalid")
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing_markers"], list(EXPECTED_MARKERS))

    @patch("scripts.fcf_sync.fetch_text", side_effect=RuntimeError("offline"))
    def test_network_failure_is_reported(self, _fetch):
        result = inspect_source("test", "https://example.invalid")
        self.assertFalse(result["ok"])
        self.assertIn("offline", result["error"])


if __name__ == "__main__":
    unittest.main()
