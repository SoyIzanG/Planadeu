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



def _first_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _team_name(value: Any) -> str:
    if isinstance(value, dict):
        value = _first_value(value, ("nom", "nombre", "name", "label", "descripcio", "descripcion"))
    return str(value or "").strip()


def normalize_modern_fixture_rows(payload: Any) -> list[dict[str, Any]]:
    """Map the current FCF frontend's common Catalan/Spanish fields to our validator."""
    rows = extract_result_rows(payload)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        home = _team_name(_first_value(row, (
            "equipLocal", "equip_local", "equipoLocal", "equipo_local",
            "local", "equipLocalNom", "nomEquipLocal", "equipo_local_nombre",
        )))
        away = _team_name(_first_value(row, (
            "equipVisitant", "equip_visitant", "equipoVisitante", "equipo_visitante",
            "visitant", "visitante", "equipVisitantNom", "nomEquipVisitant", "equipo_visitante_nombre",
        )))
        if not home or not away:
            raise ValueError("Modern FCF fixture schema is not recognized; refusing to validate/import")
        normalized.append({
            "jornada_numero": _first_value(row, ("jornada", "jornadaNumero", "jornada_numero", "matchday")),
            "equipo_local_nombre": home,
            "equipo_visitante_nombre": away,
            "fecha_partido": _first_value(row, ("data", "fecha", "date", "fecha_partido")),
            "hora_partido": _first_value(row, ("hora", "time", "hora_partido")),
            "codigo_acta": _first_value(row, ("actaId", "codigoActa", "codigo_acta")),
            "acta_cerrada": _first_value(row, ("actaTancada", "actaCerrada", "acta_cerrada")),
            "resultado_provisional": _first_value(row, ("resultatProvisional", "resultadoProvisional", "resultado_provisional")),
            "equipo_local_goles": _first_value(row, ("golsLocal", "golesLocal", "resultatLocal", "equipo_local_goles")),
            "equipo_visitante_goles": _first_value(row, ("golsVisitant", "golesVisitante", "resultatVisitant", "equipo_visitante_goles")),
        })
    return normalized


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
    competition_home = "https://www.fcf.cat/ca/competicio"
    report: dict[str, Any] = {"homepage": homepage, "reachable": False, "script_count": 0, "endpoint_candidates": []}
    try:
        roots = [homepage, competition_home]
        script_urls: list[str] = []
        for root_url in roots:
            request = urllib.request.Request(
                root_url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            )
            try:
                with urllib.request.urlopen(request, timeout=8) as response:
                    html = response.read(2_000_000).decode("utf-8", errors="replace")
                report["reachable"] = True
                script_urls.extend(urljoin(root_url, src) for src in re.findall(r"""<script[^>]+src=["']([^"']+)["']""", html, flags=re.I))
            except Exception as exc:
                report.setdefault("root_errors", []).append({"url": root_url, "error": str(exc)})
        script_urls = list(dict.fromkeys(script_urls))
        report["script_count"] = len(script_urls)
        report["script_assets"] = script_urls[:40]
        candidates: set[str] = set()
        api_routes: set[str] = set()
        api_snippets: list[dict[str, str]] = []
        pattern = re.compile(r"""["'\x60]([^"'\x60]*(?:/api/|api/|result|resultat|compet|partit|jornada|calendari|match)[^"'\x60]*)["'\x60]""", re.I)
        for script_url in script_urls[:50]:
            try:
                req = urllib.request.Request(script_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=6) as response:
                    source = response.read(1_000_000).decode("utf-8", errors="replace")
                for match in pattern.findall(source):
                    value = match.strip()
                    if value.startswith(("http://", "https://", "/")) and len(value) < 300:
                        candidates.add(urljoin(homepage, value))
                cursor = 0
                while True:
                    fetch_at = source.find("fetch(", cursor)
                    if fetch_at < 0:
                        break
                    snippet = source[fetch_at:fetch_at + 900]
                    left = snippet.find("`")
                    right = snippet.find("`", left + 1) if left >= 0 else -1
                    if left >= 0 and right > left:
                        route = snippet[left + 1:right].strip()
                        if "/api/" in route.lower() or route.startswith("/"):
                            api_routes.add(route[:350])
                    cursor = fetch_at + 6
                for token in re.finditer(r"\b(?:api|fetch\s*\(|axios|HttpClient|temporadaId|grupId)\b", source, flags=re.I):
                    snippet = source[max(0, token.start() - 120):min(len(source), token.end() + 220)]
                    if "/api/" in snippet.lower() or "axios" in snippet.lower():
                        api_snippets.append({"script": script_url, "snippet": snippet[:420]})
                    if len(api_snippets) >= 20:
                        break
            except Exception:
                continue
        report["endpoint_candidates"] = sorted(candidates)[:60]
        report["api_routes"] = sorted(api_routes)[:80]
        report["api_snippets"] = api_snippets[:20]
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
        # The current FCF site exposes a public search API used by its own UI.
        # Use it to discover competition IDs before attempting a fixture endpoint.
        search_url = homepage.replace("/es", "") + "/api/search?q=juvenil%20segona%20divisio%20grup%2029&locale=ca"
        try:
            # Reuse the site's session cookies and same-origin browser headers;
            # the public FCF frontend may reject a bare server-side API request.
            from http.cookiejar import CookieJar
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
            homepage_request = urllib.request.Request(
                homepage,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ca-ES,ca;q=0.9,es;q=0.8,en;q=0.7",
                },
            )
            with opener.open(homepage_request, timeout=10) as homepage_response:
                homepage_response.read(100_000)
            req = urllib.request.Request(
                search_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "ca-ES,ca;q=0.9,es;q=0.8,en;q=0.7",
                    "Referer": homepage,
                    "Origin": "https://www.fcf.cat",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                },
            )
            with opener.open(req, timeout=10) as response:
                raw_search = response.read(1_000_000).decode("utf-8", errors="replace")
                search_payload = json.loads(raw_search)
            report["competition_search"] = {
                "url": search_url,
                "ok": True,
                "payload": search_payload,
            }
        except Exception as exc:
            report["competition_search"] = {"url": search_url, "ok": False, "error": str(exc)}

        # The current official frontend's bundles reveal these competition API
        # routes. Probe them directly instead of guessing the legacy id_grupo.
        try:
            api_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
            with api_opener.open(homepage_request, timeout=10) as response:
                response.read(100_000)
            api_headers = {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Referer": competition_home,
                "Origin": "https://www.fcf.cat",
                "Accept-Language": "ca-ES,ca;q=0.9,es;q=0.8,en;q=0.7",
            }
            seasons_url = "https://www.fcf.cat/api/competition/temporadas"
            req = urllib.request.Request(seasons_url, headers=api_headers)
            with api_opener.open(req, timeout=10) as response:
                seasons_payload = json.loads(response.read(1_000_000).decode("utf-8", errors="replace"))
            report["official_api_seasons"] = {"url": seasons_url, "ok": True, "payload": seasons_payload}
            season_rows = seasons_payload if isinstance(seasons_payload, list) else seasons_payload.get("data", [])
            season_rows = season_rows if isinstance(season_rows, list) else []
            season_2026 = next(
                (item for item in season_rows if isinstance(item, dict) and "2026" in str(item.get("label", item.get("name", "")))),
                None,
            )
            season_ids = []
            if isinstance(season_2026, dict):
                season_ids = [str(season_2026[key]) for key in ("value", "id", "idTemporada", "temporadaId") if season_2026.get(key) is not None]
            season_param = season_ids[0] if season_ids else "2026"
            competitions_url = "https://www.fcf.cat/api/competition/competicions?" + urllib.parse.urlencode({
                "disciplinaId": "19308233",
                "temporada": season_param,
            })
            try:
                req = urllib.request.Request(competitions_url, headers=api_headers)
                with api_opener.open(req, timeout=10) as response:
                    competitions_payload = json.loads(response.read(2_000_000).decode("utf-8", errors="replace"))
                report["official_api_competitions"] = {"url": competitions_url, "ok": True, "payload": competitions_payload}
            except Exception as exc:
                report["official_api_competitions"] = {"url": competitions_url, "ok": False, "error": str(exc)}
        except Exception as exc:
            report["official_api_seasons"] = {"url": "https://www.fcf.cat/api/competition/temporadas", "ok": False, "error": str(exc)}

        # FCF's WAF returns 403 to plain urllib requests in hosted runners. Retry
        # from a real Chromium page context, which uses the same browser fetch path
        # as the public frontend. Playwright is optional for local unit tests and is
        # installed in the scheduled workflow.
        try:
            from playwright.sync_api import sync_playwright
    
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(locale="ca-ES", user_agent=USER_AGENT)
                page.goto(homepage, wait_until="domcontentloaded", timeout=25000)
                browser_probe = page.evaluate("""async () => {
                  const request = async (url) => {
                    try {
                      const response = await fetch(url, {headers: {Accept: 'application/json, text/plain, */*'}});
                      const text = await response.text();
                      let payload;
                      try { payload = JSON.parse(text); } catch { payload = text.slice(0, 500); }
                      return {url, status: response.status, ok: response.ok, payload};
                    } catch (error) { return {url, ok: false, error: String(error)}; }
                  };
                  const seasons = await request('/api/competition/temporadas');
                  const search = await request('/api/search?q=juvenil%20segona%20divisio%20grup%2029&locale=ca');
                  let season = null;
                  if (seasons.ok && Array.isArray(seasons.payload)) {
                    season = seasons.payload.find(item => String(item.label || '').includes('2026')) || null;
                  }
                  let competitions = null, selectedCompetition = null, groups = null, selectedGroup = null, matches = null, teams = null;
                  const listOf = value => Array.isArray(value) ? value : (Array.isArray(value?.data) ? value.data : []);
                  const labelOf = value => String(value?.label || value?.nombre || value?.name || value?.descripcion || '');
                  if (season && season.value != null) {
                    competitions = await request('/api/competition/competicions?disciplinaId=19308233&temporada=' + encodeURIComponent(season.value));
                    selectedCompetition = listOf(competitions?.payload).find(item => /juvenil.*segona.*divisi/i.test(labelOf(item))) || null;
                  }
                  if (selectedCompetition && selectedCompetition.value != null) {
                    groups = await request('/api/competition/grupos?competicioId=' + encodeURIComponent(selectedCompetition.value));
                    selectedGroup = listOf(groups?.payload).find(item => /grup\s*29/i.test(labelOf(item)) || String(item?.label || item?.nombre || '').trim() === '29') || null;
                  }
                  if (selectedGroup) {
                    const groupId = selectedGroup.value ?? selectedGroup.id ?? selectedGroup.grupId;
                    if (groupId != null) {
                      matches = await request('/api/competition/partidos?grupId=' + encodeURIComponent(groupId));
                      teams = await request('/api/competition/equipos?grupId=' + encodeURIComponent(groupId));
                    }
                  }
                  return {pageUrl: location.href, title: document.title, seasons, search, selectedSeason: season, competitions, selectedCompetition, groups, selectedGroup, matches, teams};
                }""")
                browser.close()
            report["browser_api_probe"] = browser_probe
        except Exception as exc:
            report["browser_api_probe"] = {"ok": False, "error": str(exc)}
    
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
    if not FCF_GROUP_ID:
        # The public competition number (e.g. Grup 29) is not the legacy API's
        # internal id. Never send "29" as if it were verified configuration.
        report["error"] = "FCF_GROUP_ID is not configured; public group number cannot safely be used as the legacy API id"
        report["modern_fcf_discovery"] = discover_modern_fcf_endpoints()
        report["ok"] = False
    else:
        try:
            matchday = int(FCF_MATCHDAY) if FCF_MATCHDAY.isdigit() else None
            payload = post_fcf_results(FCF_GROUP_ID)
            rows = extract_result_rows(payload)
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
