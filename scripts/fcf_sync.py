#!/usr/bin/env python3
"""Read-only FCF legacy API adapter and source diagnostics.

The API contract is recovered from pauruiz/fcf (2013): POST
/data/json_resultados.php with id_grupo and optional jornada. No database writes
are performed here. A group id must be configured explicitly; group number 29 is
not assumed to be the API's internal id.
"""
from __future__ import annotations

import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

FCF_API_BASE = os.getenv("FCF_API_BASE", "http://m.fcf.cat/data").rstrip("/")
FCF_RESULTS_ENDPOINT = FCF_API_BASE + "/json_resultados.php"
FCF_GROUP_ID = os.getenv("FCF_GROUP_ID", "").strip()
FCF_MATCHDAY = os.getenv("FCF_MATCHDAY", "").strip()
FUTBOTEO_URL = os.getenv(
    "FUTBOTEO_URL",
    "https://futbuteo.com/catalunya/resultados/juvenil-segona-divisio/grup-29/",
)
USER_AGENT = "PlanadeuFixtureMonitor/1.0 (+https://github.com/SoyIzanG/Planadeu)"


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def post_fcf_results(group_id: str, matchday: int | None = None, attempts: int = 3) -> Any:
    """Call the legacy FCF JSON API using its documented historical form fields."""
    if not group_id or not group_id.isdigit():
        raise ValueError("FCF_GROUP_ID must be configured as the official API group code")
    fields: dict[str, str] = {"id_grupo": group_id}
    if matchday is not None:
        if not 1 <= matchday <= 30:
            raise ValueError("FCF_MATCHDAY must be between 1 and 30")
        fields["jornada"] = str(matchday)
    body = urllib.parse.urlencode(fields).encode("ascii")
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            FCF_RESULTS_ENDPOINT,
            data=body,
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/plain,*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.status
                raw = response.read(4_000_000)
                if not 200 <= status < 300:
                    raise RuntimeError(f"FCF API returned HTTP {status}")
                try:
                    return json.loads(raw.decode("utf-8-sig"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    excerpt = raw[:300].decode("utf-8", errors="replace")
                    raise RuntimeError(f"FCF API did not return JSON: {excerpt}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"FCF API request failed after {attempts} attempts: {last_error}")


def extract_result_rows(payload: Any) -> list[dict[str, Any]]:
    """Accept the array and common envelope shapes used by legacy JSON APIs."""
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for key in ("resultados", "results", "data", "partidos"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                rows = candidate
                break
        if rows is None:
            raise ValueError("FCF API JSON has no results array")
    else:
        raise ValueError("FCF API JSON root must be an object or array")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("FCF API results contain non-object entries")
    return rows


def result_matchday(row: dict[str, Any]) -> int | None:
    value = row.get("jornada_numero", row.get("jornada", row.get("matchday")))
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def summarize_results(rows: list[dict[str, Any]], matchday: int | None) -> dict[str, Any]:
    """Return a safe structural summary without treating provisional scores as final."""
    selected = [row for row in rows if matchday is None or result_matchday(row) == matchday]
    teams: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for row in selected:
        home = str(row.get("equipo_local_nombre") or "").strip()
        away = str(row.get("equipo_visitante_nombre") or "").strip()
        if home:
            teams.add(normalize_text(home))
        if away:
            teams.add(normalize_text(away))
        normalized.append({
            "matchday": result_matchday(row),
            "home": home or None,
            "away": away or None,
            "date": row.get("fecha_partido"),
            "time": row.get("hora_partido"),
            "acta_id": row.get("codigo_acta"),
            "acta_closed": row.get("acta_cerrada"),
            "provisional": row.get("resultado_provisional"),
            "home_goals": row.get("equipo_local_goles"),
            "away_goals": row.get("equipo_visitante_goles"),
        })
    errors: list[str] = []
    if matchday is not None:
        if len(selected) != 7:
            errors.append(f"expected_7_fixtures_got_{len(selected)}")
        if len(teams) not in (14, 15):
            errors.append(f"expected_14_or_15_distinct_teams_got_{len(teams)}")
        if any(not item["home"] or not item["away"] for item in normalized):
            errors.append("fixture_missing_team_name")
    elif not selected:
        errors.append("api_returned_no_results")
    return {
        "requested_matchday": matchday,
        "fixture_count": len(selected),
        "distinct_team_count": len(teams),
        "fixtures": normalized,
        "validation_errors": errors,
        "ok": not errors,
    }


def inspect_futbuteo(url: str = FUTBOTEO_URL) -> dict[str, Any]:
    """Secondary-source note only: its public page may require client-side JS."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            excerpt = response.read(200_000).decode("utf-8", errors="replace")
        challenge = "necesitas tener activado javascript" in normalize_text(excerpt) or "sessionstorage" in excerpt.lower()
        return {
            "url": url,
            "reachable": True,
            "client_side_challenge": challenge,
            "usable_for_server_side_import": not challenge,
            "note": "Secondary cross-check only; does not block official FCF API import." if challenge else "Page reachable; parser not yet configured.",
        }
    except Exception as exc:
        return {"url": url, "reachable": False, "error": str(exc), "note": "Secondary source only."}


def discover_modern_fcf_endpoints() -> dict[str, Any]:
    """Inspect public FCF page assets for current API endpoint hints, read-only."""
    import re
    from urllib.parse import urljoin

    homepage = "https://www.fcf.cat/es"
    report: dict[str, Any] = {"homepage": homepage, "reachable": False, "script_count": 0, "endpoint_candidates": []}
    try:
        request = urllib.request.Request(homepage, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urllib.request.urlopen(request, timeout=8) as response:
            html = response.read(2_000_000).decode("utf-8", errors="replace")
        report["reachable"] = True
        script_urls = [urljoin(homepage, src) for src in re.findall(r"""<script[^>]+src=["']([^"']+)["']""", html, flags=re.I)]
        report["script_count"] = len(script_urls)
        candidates: set[str] = set()
        pattern = re.compile(r"""["']([^"']*(?:api|result|resultat|compet|partit|jornada|calendari|match)[^"']*)["']""", re.I)
        for script_url in script_urls[:15]:
            try:
                req = urllib.request.Request(script_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=6) as response:
                    source = response.read(1_000_000).decode("utf-8", errors="replace")
                for match in pattern.findall(source):
                    value = match.strip()
                    if value.startswith(("http://", "https://", "/")) and len(value) < 300:
                        candidates.add(urljoin(homepage, value))
            except Exception:
                continue
        report["endpoint_candidates"] = sorted(candidates)[:40]
        probes: list[dict[str, Any]] = []
        for page_url in sorted(candidates):
            if "/competicio?" not in page_url or len(probes) >= 10:
                continue
            try:
                req = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
                with urllib.request.urlopen(req, timeout=6) as response:
                    page = response.read(1_500_000).decode("utf-8", errors="replace")
                    status = response.status
                page_text = normalize_text(re.sub(r"<[^>]+>", " ", page))
                probes.append({
                    "url": page_url,
                    "http_status": status,
                    "juvenil_segona_divisio": "juvenil segona divisio" in page_text,
                    "grup_29": "grup 29" in page_text,
                    "planadeu": "planadeu" in page_text,
                    "can_trias": "can trias" in page_text,
                    "excerpt": re.sub(r"\\s+", " ", re.sub(r"<[^>]+>", " ", page))[:350],
                })
            except Exception as exc:
                probes.append({"url": page_url, "error": str(exc)})
        report["competition_page_probes"] = probes
    except Exception as exc:
        report["error"] = str(exc)
    return report


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "mode": "read-only-fcf-api-preflight",
        "database_modified": False,
        "official_source": {
            "url": FCF_RESULTS_ENDPOINT,
            "api_contract": "POST id_grupo; optional jornada",
            "group_id_configured": bool(FCF_GROUP_ID),
            "group_id_source": "repository_variable" if FCF_GROUP_ID else "candidate_probe_29_only",
            "requested_matchday": int(FCF_MATCHDAY) if FCF_MATCHDAY.isdigit() else None,
        },
        "secondary_source": inspect_futbuteo(),
        "notes": [
            "This command does not create or update fixtures, scores, standings, or player statistics.",
            "The internal FCF group code must be configured; it is not assumed to equal public group number 29.",
            "The legacy API contract comes from https://github.com/pauruiz/fcf and must be live-verified before enabling writes.",
        ],
    }
    try:
        matchday = int(FCF_MATCHDAY) if FCF_MATCHDAY.isdigit() else None
        # Probe public group number 29 only when no verified internal code is set.
        # Query all rounds so the team identity check also works when a team rests.
        group_id = FCF_GROUP_ID or "29"
        payload = post_fcf_results(group_id)
        rows = extract_result_rows(payload)
        if not FCF_GROUP_ID:
            team_names = {normalize_text(str(row.get(field) or "")) for row in rows for field in ("equipo_local_nombre", "equipo_visitante_nombre")}
            if not any("planadeu" in name for name in team_names) or not any("can trias" in name for name in team_names):
                raise ValueError("Candidate API group id 29 did not identify both Planadeu and Can Trias; set FCF_GROUP_ID to the verified internal code")
        summary = summarize_results(rows, matchday)
        report["official_source"].update({"http_json_ok": True, "api_rows_returned": len(rows), **summary})
        report["ok"] = summary["ok"]
        if not summary["ok"]:
            report["error"] = "FCF API response failed structural validation"
    except Exception as exc:
        report["official_source"]["http_json_ok"] = False
        report["error"] = str(exc)
        report["modern_fcf_discovery"] = discover_modern_fcf_endpoints()
        report["ok"] = False
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
