#!/usr/bin/env python3
"""Read-only health check for Planadeu football data sources.

This first stage deliberately does not write to the database. It validates that
source pages are reachable and contain expected competition markers before a
separate, tested importer is allowed to mutate fixtures or results.
"""
from __future__ import annotations

import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

FUTBOTEO_URL = os.getenv(
    "FUTBOTEO_URL",
    "https://futbuteo.com/catalunya/resultados/juvenil-segona-divisio/grup-29/",
)
FCF_URL = os.getenv(
    "FCF_URL",
    "https://www.fcf.cat/resultats/2627/futbol-11/juvenil-segona-divisio/grup-29",
)
EXPECTED_MARKERS = ("juvenil segona divisio", "grup 29")


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def fetch_text(url: str, attempts: int = 3) -> tuple[int, str]:
    """Fetch a public page with bounded retries and a descriptive user agent."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "PlanadeuFixtureMonitor/1.0 (+https://github.com/SoyIzanG/Planadeu)",
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(4_000_000)
                charset = response.headers.get_content_charset() or "utf-8"
                parser = TextExtractor()
                parser.feed(raw.decode(charset, errors="replace"))
                return response.status, parser.text
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Request failed after {attempts} attempts: {last_error}")


def normalize_text(value: str) -> str:
    """Case-fold text and remove diacritics so Catalan/Spanish accents match."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def inspect_source(name: str, url: str) -> dict[str, Any]:
    try:
        status, text = fetch_text(url)
        normalized = normalize_text(text)
        missing = [marker for marker in EXPECTED_MARKERS if marker not in normalized]
        return {
            "source": name,
            "url": url,
            "http_status": status,
            "reachable": 200 <= status < 300,
            "competition_markers_found": not missing,
            "missing_markers": missing,
            "page_excerpt": text[:500],
            "ok": 200 <= status < 300 and not missing,
        }
    except Exception as exc:  # keep per-source diagnostics; do not hide failure
        return {
            "source": name,
            "url": url,
            "reachable": False,
            "competition_markers_found": False,
            "error": str(exc),
            "ok": False,
        }


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only-preflight",
        "database_modified": False,
        "sources": [
            inspect_source("futboteo", FUTBOTEO_URL),
            inspect_source("fcf_official", FCF_URL),
        ],
        "notes": [
            "This run does not create or update fixtures, results, standings, or player statistics.",
            "Source reachability is not proof that every fixture/result is complete or official.",
            "The legacy pauruiz/fcf project uses 2013-era HTTP endpoints and is not called automatically.",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(item["ok"] for item in report["sources"]) else 1


if __name__ == "__main__":
    sys.exit(main())
