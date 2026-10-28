#!/usr/bin/env python3
"""Conservative sync for the club-agreed Juvenil C, Grup 29 schedule.

Planadeu is part of the agreed 2026-2027 roster even if public listings omit it.
A round is importable only with all 16 teams and 8 fixtures, including Planadeu.
Public pages with 15 teams/7 fixtures and a bye are incomplete and are never
written. Writes are disabled unless ENABLE_FOOTBALL_IMPORT=true is set.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
import html as html_lib
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg2
from psycopg2.extras import RealDictCursor

BASE_URL = "https://futbuteo.com/catalunya/resultados/juvenil-segona-divisio/grup-29/"
ELFUTBOL_URL = os.getenv("ELFUTBOL_URL", "https://elfutbol.co/es/competitions/juvenil-segona-divisio/grup-29?results=all&season=2627&tab=results")
CLUB_FIXTURES_URL = os.getenv("CLUB_FIXTURES_URL", "").strip()
CLUB_FIXTURES_TOKEN = os.getenv("CLUB_FIXTURES_TOKEN", "").strip()
SEASON_NAME = "2026-2027"
SEASON_ID_ENV = os.getenv("SEASON_ID", "").strip()
ENABLE_IMPORT = os.getenv("ENABLE_FOOTBALL_IMPORT", "false").strip().lower() == "true"
EXPECTED_TEAMS = 16
EXPECTED_FIXTURES = 8
# Futbuteo uses j=<actual round number>; the page itself labels Jornada 5 for ?j=5.
SYNC_MATCHDAY_ENV = os.getenv("SYNC_MATCHDAY", "").strip()
MATCHDAYS = [int(SYNC_MATCHDAY_ENV)] if SYNC_MATCHDAY_ENV.isdigit() and 1 <= int(SYNC_MATCHDAY_ENV) <= 30 else range(1, 31)
USER_AGENT = "Planadeu-LeagueSync/1.0 (+scheduled fixture verification)"
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)")
ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})(?:[T ](\d{1,2}:\d{2})(?::\d{2})?)?\b")
SCORE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[-–:]\s*(\d{1,2})(?!\d)")
CANDIDATE_CLASS_RE = re.compile(r"(match|fixture|partit|result|game|joc|event|row)", re.I)
MONTHS = {
    "gen": 1, "gener": 1, "ene": 1, "enero": 1,
    "feb": 2, "febrer": 2, "febrero": 2,
    "mar": 3, "marc": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "mai": 5, "mayo": 5,
    "jun": 6, "juny": 6, "junio": 6,
    "jul": 7, "juliol": 7, "julio": 7,
    "ago": 8, "agost": 8, "agosto": 8,
    "set": 9, "sep": 9, "setembre": 9, "septiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "novembre": 11, "noviembre": 11,
    "des": 12, "dic": 12, "desembre": 12, "diciembre": 12,
}
SHORT_DATE_RE = re.compile(r"\b(\d{1,2})\s+(gen(?:er)?|ene(?:ro)?|feb(?:rer|rero)?|mar(?:ç|c|zo)?|abr(?:il)?|mai|mayo|jun(?:y|io)?|jul(?:iol|io)?|ago(?:st|sto)?|set(?:embre)?|sep(?:tiembre)?|oct(?:ubre)?|nov(?:embre|iembre)?|des(?:embre)?|dic(?:iembre)?)\b", re.I)
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
# Names used by Futbuteo can differ from the club names stored in Supabase.
TEAM_ALIASES = {
    "cef viladecavalls": ["escola de futbol viladecavalls"],
    "club natacio terrassa": ["natacio terrassa"],
    "terrassa fc": ["fundacio terrassa fc 1906"],
    "club de futbol vacarisses": ["vacarisses club futbol", "vacarisses"],
    "club de futbol matadepera": ["matadepera fc", "matadepera f c"],
    "unio fb jabac terrassa": ["unio f base jabac i terrassa", "jabac i terrassa"],
    "cp san cristobal": ["san cristobal cp", "san cristobal"],
    "ue rubi": ["rubi ue", "rubi u e", "rubi u e c"],
    "ud can trias": ["can trias ud", "can trias"],
    "can parellada cd": ["can parellada"],
    "pueblo nuevo 2002 cf": ["pueblo nuevo 2002"],
    "athletic matadeperenc": ["matadeperenc athletic", "matadeperenc"],
    "sant pere nord cf": ["sant pere nord"],
    "escola futbol can boada": ["escola futbol can boada"],
    "escola pia terrassa": ["escola pia terrassa"],
    # The agreed team must be present in every round; do not alias another
    # Planadeu squad (for example a public page that says Grup 28) to Juvenil C.
    "ue planadeu": [
        "planadeu c",
        "planadeu roureda unio esportiva futbol c",
        "planadeu unio esportiva club futbol c",
    ],
}


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def compact(value: str) -> str:
    """Normalize punctuation/spacing variants such as 'U.E. Rubí' vs 'UE Rubí'."""
    return norm(value).replace(" ", "")


class CandidateParser(HTMLParser):
    """Collect likely fixture rows/cards without assuming one specific HTML layout."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.candidates = []
        self.full_text = []
        self.current_date = None
        self.current_matchday = None
        self.has_round_labels = False
        self.recent_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "")
        # Futbuteo changes class names frequently. Include all common card/container
        # elements and let the two-team + complete-round checks reject false positives.
        # Do not treat every wrapper div as a fixture: the page contains
        # large wrappers around standings, team tables and news. Only collect
        # semantically named match/fixture nodes and standard table/list rows.
        candidate = tag.lower() in {"tr", "li"} or (
            tag.lower() in {"div", "article", "section"}
            and CANDIDATE_CLASS_RE.search(classes or "") is not None
        )
        node = {
            "tag": tag.lower(), "attrs": attrs, "text": [],
            "date_context": self.current_date,
            "matchday_context": self.current_matchday,
        } if candidate else None
        if node:
            self.stack.append(node)
        for node in self.stack:
            for key in ("datetime", "data-date", "data-kickoff", "title", "aria-label"):
                val = attrs.get(key)
                if val:
                    node["text"].append(val)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                closed = self.stack[i:]
                del self.stack[i:]
                for node in closed:
                    text = " ".join(node["text"])
                    if text.strip():
                        self.candidates.append((text, node["date_context"], node["matchday_context"]))
                break

    def handle_data(self, data):
        if data.strip():
            self.full_text.append(data.strip())
            self.recent_text = (self.recent_text + " " + data.strip())[-180:]
            # Some providers expose all rounds on one SSR page. Capture the
            # nearest round heading so the fallback can safely select one round.
            round_heading = re.search(r"\b(?:jornada|matchday|round)\s*([0-9]{1,2})\b", data, re.I)
            if round_heading:
                self.current_matchday = int(round_heading.group(1))
                self.has_round_labels = True
                for node in self.stack:
                    if node["matchday_context"] is None:
                        node["matchday_context"] = self.current_matchday
            # The source labels fixture sections with yearless headings such as
            # "Sábado 31 oct". Remember that date for following fixture cards.
            short = SHORT_DATE_RE.search(self.recent_text)
            if short:
                day = int(short.group(1))
                month_token = norm(short.group(2)).replace(" ", "")
                month = MONTHS.get(month_token)
                if month:
                    year = 2026 if month >= 8 else 2027
                    try:
                        self.current_date = date(year, month, day)
                        for node in self.stack:
                            if node["date_context"] is None:
                                node["date_context"] = self.current_date
                    except ValueError:
                        pass
            for node in self.stack:
                node["text"].append(data.strip())


_PLAYWRIGHT = None
_BROWSER = None
_BROWSER_PAGE = None
_ELFUTBOL_HTML = None
_CLUB_FEED_PAYLOAD = None


def _visible_text(html: str) -> str:
    """Get rendered-ish body text without script/style payloads or metadata."""
    value = html_lib.unescape(html or "")
    value = re.sub(r"<(script|style|noscript|template)\b[^>]*>.*?</\1\s*>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<!--.*?-->", " ", value, flags=re.S)
    return norm(re.sub(r"<[^>]+>", " ", value))


def _looks_like_challenge(html: str) -> bool:
    lower = (html or "").lower()
    visible = _visible_text(html)
    explicit = (
        "necesitas tener activado javascript" in visible
        or "please enable javascript to continue" in visible
        or "checking your browser" in visible
        or "just a moment" in visible
        or "request blocked" in visible
        or "access denied" in visible
    )
    # A server-rendered JS shell may embed the whole schedule in a script tag.
    # Such hidden payload must not trick this check into assuming the page is
    # rendered. Require actual body text plus multiple known roster names.
    group_visible = (
        "juvenil segona divisio" in visible
        and "grup 29" in visible
        and len(visible) > 250
    )
    weak_challenge = (
        ("sessionstorage" in lower or "javascript" in lower or "__next_data__" in lower)
        and not group_visible
    )
    return explicit or weak_challenge


def _is_captcha(html: str) -> bool:
    lower = (html or "").lower()
    return any(token in lower for token in ("cf-turnstile", "g-recaptcha", "hcaptcha", "captcha challenge"))


def _get_browser_page():
    global _PLAYWRIGHT, _BROWSER, _BROWSER_PAGE
    if _BROWSER_PAGE is None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("La fuente exige navegador; instala Playwright y Chromium.") from exc
        _PLAYWRIGHT = sync_playwright().start()
        _BROWSER = _PLAYWRIGHT.chromium.launch(headless=True)
        _BROWSER_PAGE = _BROWSER.new_page(
            locale="ca-ES",
            user_agent=USER_AGENT,
            viewport={"width": 1365, "height": 900},
        )
    return _BROWSER_PAGE


def _fetch_html(url: str) -> str:
    direct_error = None
    try:
        request = Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ca-ES,ca;q=0.9,es;q=0.8,en;q=0.7",
        })
        with urlopen(request, timeout=25) as response:
            html = response.read(4_000_000).decode("utf-8", errors="replace")
        if response.status == 200 and not _looks_like_challenge(html):
            return html
        if _is_captcha(html):
            raise RuntimeError("La fuente exige resolver un CAPTCHA; no se intenta eludirlo.")
    except Exception as exc:
        direct_error = exc

    # Execute the site's normal JavaScript/cookie flow when the raw HTML is
    # only a client-side shell. This is not a CAPTCHA solver or proxy bypass.
    try:
        page = _get_browser_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1200)
        html = page.content()
        if response is not None and response.status >= 400:
            raise RuntimeError(f"El navegador recibió HTTP {response.status}")
        if _is_captcha(html):
            raise RuntimeError("La fuente exige resolver un CAPTCHA; no se intenta eludirlo.")
        if _looks_like_challenge(html):
            raise RuntimeError("El contenido sigue siendo una pantalla de JavaScript/desafío.")
        return html
    except Exception as browser_error:
        if isinstance(browser_error, RuntimeError):
            raise
        raise RuntimeError(
            f"No se pudo leer la fuente ni por HTTP ni en navegador ({type(direct_error).__name__ if direct_error else 'HTTP'} / {type(browser_error).__name__})."
        ) from browser_error


def fetch_club_feed() -> dict:
    """Fetch and cache an authorised club-owned JSON export; never bypass a challenge."""
    global _CLUB_FEED_PAYLOAD
    if _CLUB_FEED_PAYLOAD is not None:
        return _CLUB_FEED_PAYLOAD
    if not CLUB_FIXTURES_URL:
        raise RuntimeError("No está configurada CLUB_FIXTURES_URL")
    if not CLUB_FIXTURES_URL.lower().startswith("https://"):
        raise RuntimeError("CLUB_FIXTURES_URL debe usar HTTPS")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if CLUB_FIXTURES_TOKEN:
        headers["Authorization"] = f"Bearer {CLUB_FIXTURES_TOKEN}"
    request = Request(CLUB_FIXTURES_URL, headers=headers)
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"El feed del club respondió HTTP {response.status}")
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000:
        raise RuntimeError("El feed del club supera el límite de 4 MB")
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("El feed del club debe tener un objeto JSON en la raíz")
    _CLUB_FEED_PAYLOAD = payload
    return payload


def _feed_kickoff(fixture: dict) -> tuple[datetime | None, bool]:
    """Parse a date/time without inventing a kickoff hour."""
    kickoff_value = fixture.get("kickoff")
    date_value = fixture.get("date") or fixture.get("fecha")
    time_value = fixture.get("time") or fixture.get("hora")

    if isinstance(kickoff_value, str) and kickoff_value.strip():
        raw = kickoff_value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None, False
        has_explicit_time = "T" in raw or " " in raw
        confirmed = bool(fixture.get("kickoff_confirmed", has_explicit_time))
        if parsed.tzinfo is not None:
            # Keep the wall-clock time as supplied; feed providers should publish
            # local Catalonia time (Europe/Madrid), since the app stores local naive time.
            parsed = parsed.replace(tzinfo=None)
        if parsed.time().isoformat() == "00:00:00" and fixture.get("kickoff_confirmed") is not True:
            confirmed = False
        if not confirmed:
            parsed = parsed.replace(hour=12, minute=0, second=0, microsecond=0)
        return parsed, confirmed

    if not isinstance(date_value, str) or not date_value.strip():
        return None, False
    try:
        day = date.fromisoformat(date_value.strip()[:10])
    except ValueError:
        return None, False
    confirmed = False
    hour, minute = 12, 0
    if isinstance(time_value, str) and TIME_RE.fullmatch(time_value.strip()):
        hour, minute = map(int, time_value.strip().split(":"))
        confirmed = not (hour == 0 and minute == 0)
        if fixture.get("kickoff_confirmed") is True:
            confirmed = True
    kickoff = datetime(day.year, day.month, day.day, hour, minute)
    if not confirmed:
        kickoff = kickoff.replace(hour=12, minute=0)
    return kickoff, confirmed


def parse_club_feed(payload: dict, official_teams: list[str], target_matchday: int):
    """Validate a club-owned JSON schedule with the same strict group safeguards."""
    season_value = str(payload.get("season") or "").strip().replace("/", "-")
    if season_value not in {"2026-2027", "2026-27", "26-27"}:
        return None, "el feed del club no confirma la temporada 2026-2027"
    competition = norm(str(payload.get("competition") or ""))
    expected_competition = norm("Juvenil Segona Divisió Grup 29")
    if expected_competition not in competition:
        return None, "el feed del club no confirma Juvenil Segona Divisió Grup 29"

    roster = payload.get("teams")
    if not isinstance(roster, list) or len(roster) != EXPECTED_TEAMS:
        return None, f"el feed del club debe declarar exactamente {EXPECTED_TEAMS} equipos"
    official_by_norm = {norm(name): name for name in official_teams}
    canonical_roster = [official_by_norm.get(norm(str(name))) for name in roster]
    if any(name is None for name in canonical_roster):
        return None, "el feed del club contiene un nombre de equipo sin correspondencia exacta"
    if len(set(canonical_roster)) != EXPECTED_TEAMS or set(canonical_roster) != set(official_teams):
        return None, "la plantilla del feed del club no coincide con los 16 equipos de la temporada"

    fixture_rows = payload.get("fixtures")
    if not isinstance(fixture_rows, list):
        matchdays = payload.get("matchdays")
        if isinstance(matchdays, list):
            fixture_rows = []
            for matchday_row in matchdays:
                if not isinstance(matchday_row, dict):
                    return None, "el feed contiene una jornada mal formada"
                group_round = matchday_row.get("matchday", matchday_row.get("jornada"))
                nested = matchday_row.get("fixtures", matchday_row.get("partidos"))
                if not isinstance(nested, list):
                    return None, "una jornada del feed no contiene una lista de partidos"
                for fixture in nested:
                    if isinstance(fixture, dict):
                        fixture_rows.append({**fixture, "matchday": fixture.get("matchday", group_round)})
                    else:
                        return None, "el feed contiene un partido mal formado"
        else:
            return None, "el feed no contiene fixtures ni matchdays"

    selected = []
    for fixture in fixture_rows:
        if not isinstance(fixture, dict):
            return None, "el feed contiene un partido mal formado"
        raw_matchday = fixture.get("matchday", fixture.get("jornada"))
        try:
            fixture_matchday = int(raw_matchday)
        except (TypeError, ValueError):
            return None, "cada partido del feed debe declarar su jornada"
        if fixture_matchday != target_matchday:
            continue
        home = official_by_norm.get(norm(str(fixture.get("home") or fixture.get("local") or "")))
        away = official_by_norm.get(norm(str(fixture.get("away") or fixture.get("visitant") or "")))
        if not home or not away or home == away:
            return None, "el feed contiene equipos desconocidos o un partido de un equipo contra sí mismo"
        kickoff, kickoff_confirmed = _feed_kickoff(fixture)
        if kickoff is None:
            return None, "hay un partido sin fecha válida; no se importa la jornada"
        final = fixture.get("result_is_final") is True and fixture.get("provisional") is not True
        hg = fixture.get("home_goals", fixture.get("goles_local"))
        ag = fixture.get("away_goals", fixture.get("goles_visitante"))
        if final:
            def strict_goal(value):
                if isinstance(value, bool):
                    raise ValueError("boolean score")
                if isinstance(value, int):
                    score = value
                elif isinstance(value, str) and re.fullmatch(r"\d{1,2}", value.strip()):
                    score = int(value.strip())
                else:
                    raise ValueError("non-integer score")
                if score < 0:
                    raise ValueError("negative score")
                return score
            try:
                hg, ag = strict_goal(hg), strict_goal(ag)
            except ValueError:
                return None, "un resultado marcado como final no tiene dos goles enteros válidos"
        else:
            hg, ag = None, None
        selected.append({
            "home": home,
            "away": away,
            "kickoff": kickoff,
            "kickoff_confirmed": kickoff_confirmed,
            "home_goals": hg,
            "away_goals": ag,
            "result_is_final": final,
            "is_played": final,
            "source": "Club feed",
        })

    used = [name for fixture in selected for name in (fixture["home"], fixture["away"])]
    if len(selected) != EXPECTED_FIXTURES:
        return None, f"jornada del feed del club incompleta: {len(selected)} partidos; se exigen {EXPECTED_FIXTURES}"
    if len(set(used)) != EXPECTED_TEAMS or set(used) != set(official_teams):
        return None, "los ocho partidos del feed no cubren a los 16 equipos exactamente una vez"
    if not any("planadeu" in norm(team) for team in used):
        return None, "la jornada del feed no contiene Planadeu"
    if len({frozenset((f["home"], f["away"])) for f in selected}) != EXPECTED_FIXTURES:
        return None, "el feed repite un emparejamiento dentro de la jornada"
    return {"fixtures": selected, "bye": None, "source": "Club feed"}, None


def fetch_page(j_value: int) -> str:
    return _fetch_html(f"{BASE_URL}?j={j_value}")

def futbuteo_query_for_matchday(matchday: int) -> int:
    """Futbuteo's j parameter is the actual displayed matchday number."""
    if not 1 <= matchday <= 30:
        raise ValueError("La jornada debe estar entre 1 y 30")
    return matchday




def fetch_elfutbol_page() -> str:
    """Fallback provider: public whole-season group page, filtered by round."""
    global _ELFUTBOL_HTML
    if _ELFUTBOL_HTML is None:
        _ELFUTBOL_HTML = _fetch_html(ELFUTBOL_URL)
    return _ELFUTBOL_HTML


def close_fetch_browser() -> None:
    global _PLAYWRIGHT, _BROWSER, _BROWSER_PAGE
    try:
        if _BROWSER is not None:
            _BROWSER.close()
        if _PLAYWRIGHT is not None:
            _PLAYWRIGHT.stop()
    finally:
        _PLAYWRIGHT = _BROWSER = _BROWSER_PAGE = None


def parse_date(text: str):
    iso = ISO_DATE_RE.search(text)
    if iso:
        day = date.fromisoformat(iso.group(1))
        clock = iso.group(2) or "12:00"
        hour, minute = map(int, clock.split(":"))
        return datetime(day.year, day.month, day.day, hour, minute)
    match = DATE_RE.search(text)
    if match:
        d, m, y = map(int, match.groups())
        try:
            return datetime(y, m, d, 12, 0)
        except ValueError:
            return None
    return None


def parse_score(text: str, kickoff):
    # Remove dates first so the date's hyphens cannot be mistaken for a score.
    cleaned = ISO_DATE_RE.sub(" ", text)
    cleaned = DATE_RE.sub(" ", cleaned)
    # A kickoff such as 12:00 must never be interpreted as a 12–0 score.
    cleaned = TIME_RE.sub(" ", cleaned)
    scores = []
    for match in SCORE_RE.finditer(cleaned):
        a, b = map(int, match.groups())
        if a <= 30 and b <= 30:
            scores.append((a, b))
    return scores[-1] if scores else (None, None)


def _find_resting_team(full_text: str, team_lookup: dict[str, str], planadeu_name: str):
    """Identify the named team immediately associated with a public 'Descans' slot."""
    normalized = norm(full_text)
    for marker in re.finditer(r"\b(?:descans(?:a)?|rest(?:s|ing)?)\b", normalized, re.I):
        before = normalized[max(0, marker.start() - 110):marker.start()]
        after = normalized[marker.end():marker.end() + 140]
        hits = []
        for alias, team in team_lookup.items():
            if not alias or team == planadeu_name:
                continue
            p_after = after.find(alias)
            if p_after >= 0:
                hits.append((p_after, -len(alias), team))
                continue
            p_before = before.rfind(alias)
            if p_before >= 0:
                distance = len(before) - (p_before + len(alias))
                hits.append((distance, -len(alias), team))
        if hits:
            hits.sort(key=lambda hit: (hit[0], hit[1]))
            best = hits[0][:2]
            closest = {team for distance, alias_len, team in hits if (distance, alias_len) == best}
            if len(closest) == 1:
                return closest.pop()
    return None


def parse_round(html: str, official_teams: list[str], target_matchday: int, source_name: str):
    # Script bundles may contain the entire season as hidden JSON. They must
    # not affect round/date context or be mistaken for visible fixture cards.
    rendered_html = re.sub(
        r"<(script|style|noscript|template)\\b[^>]*>.*?</\\1\\s*>",
        " ",
        html or "",
        flags=re.I | re.S,
    )
    parser = CandidateParser()
    parser.feed(rendered_html)
    visible_html = html_lib.unescape(re.sub(r"<[^>]+>", " ", rendered_html))
    visible_text = _visible_text(rendered_html)
    if "juvenil segona divisio" not in visible_text or not re.search(r"\bgrup 29\b", visible_text):
        return None, "la página no confirma Juvenil Segona Divisió, Grup 29"
    if not any(token in visible_text for token in ("2026 27", "2026 2027", "temporada 26 27")):
        return None, "la página no confirma la temporada 2026-2027"

    team_lookup = {norm(team): team for team in official_teams}
    # Add only known aliases for canonical database teams. The current public
    # "Planadeu A" page in Grup 28 is deliberately NOT an alias for Juvenil C.
    for team in official_teams:
        team_compact = compact(team)
        for canonical_key, aliases in TEAM_ALIASES.items():
            if team_compact == compact(canonical_key):
                for alias in aliases:
                    team_lookup[norm(alias)] = team

    fixtures = {}
    for candidate, date_context, candidate_matchday in parser.candidates:
        # Futbuteo's round-specific ?j= URL already selects this round. The
        # same page also contains news and next-round headings, so a global
        # has_round_labels flag can filter out every current-round card.
        # Only apply per-card heading filtering to the whole-season provider.
        if parser.has_round_labels and candidate_matchday != target_matchday:
            continue
        candidate_norm = norm(candidate)
        # Keep source text order (home first, away second) rather than the order
        # of database team IDs. Prefer the longest alias at the same character
        # position so "Can Trias B" is not confused with "Can Trias".
        hits_by_team = {}
        for alias, team in team_lookup.items():
            if not alias:
                continue
            position = candidate_norm.find(alias)
            if position < 0:
                continue
            current = hits_by_team.get(team)
            rank = (position, -len(alias))
            if current is None or rank < current[0]:
                hits_by_team[team] = (rank, alias)
        hits = sorted(
            ((rank[0], rank[1], team, alias) for team, (rank, alias) in hits_by_team.items()),
            key=lambda item: (item[0], item[1]),
        )
        ordered_teams = []
        occupied_until = -1
        for position, negative_length, team, alias in hits:
            if position < occupied_until:
                continue
            if team in ordered_teams:
                continue
            ordered_teams.append(team)
            occupied_until = position + len(alias)
        if len(ordered_teams) != 2:
            continue

        kickoff = parse_date(candidate)
        date_known = kickoff is not None
        clock_match = TIME_RE.search(candidate)
        if kickoff is None and date_context is not None:
            if clock_match:
                hour, minute = map(int, clock_match.groups())
                kickoff = datetime(date_context.year, date_context.month, date_context.day, hour, minute)
            else:
                # DB requires a timestamp, but the UI hides time while this flag
                # is false. Noon is only a storage placeholder, never a claimed kickoff.
                kickoff = datetime(date_context.year, date_context.month, date_context.day, 12, 0)
            date_known = True
        if kickoff is None or not date_known:
            continue
        kickoff_confirmed = bool(clock_match)

        hg, ag = parse_score(candidate, kickoff)
        final_status = bool(
            re.search(r"(?<![a-z])ft(?=\s|\d|$)", candidate, re.I)
            or re.search(r"\b(?:final|finalitzat|finalizada|finalizado|finished|acta tancada)\b", candidate, re.I)
        )
        result_is_final = hg is not None and ag is not None and final_status
        if not result_is_final:
            # Never turn a live/provisional display into an official score.
            hg, ag = None, None

        key = frozenset(ordered_teams)
        fixture = {
            "home": ordered_teams[0],
            "away": ordered_teams[1],
            "kickoff": kickoff,
            "kickoff_confirmed": kickoff_confirmed,
            "home_goals": hg,
            "away_goals": ag,
            "result_is_final": result_is_final,
            "is_played": result_is_final,
            "source": source_name,
        }
        existing = fixtures.get(key)
        # Prefer the most complete nested candidate for the same fixture.
        if existing is None or (
            (not existing["kickoff_confirmed"] and fixture["kickoff_confirmed"])
            or (not existing["result_is_final"] and fixture["result_is_final"])
        ):
            fixtures[key] = fixture

    fixtures_list = list(fixtures.values())
    full_text = " ".join(parser.full_text)
    bye_match = re.search(r"\bdescans(?:a)?\b|\brest(?:s|ing)?\b", full_text, re.I)
    used = [team for fixture in fixtures_list for team in (fixture["home"], fixture["away"])]
    planadeu_names = [team for team in official_teams if "planadeu" in norm(team)]
    planadeu_name = planadeu_names[0] if len(planadeu_names) == 1 else None

    # The public schedule has 15 teams and one "Descans" slot. The club has
    # confirmed the agreed roster has 16 teams including Planadeu C. Reconstruct
    # the missing pairing only when (a) exactly seven public fixtures parse,
    # (b) those fixtures cover 14 database teams, (c) the only non-Planadeu team
    # not used is the same team named beside "Descans", and (d) the requested
    # group/season and round are visible. The extra fixture stays explicitly
    # pending; no kickoff time or score is invented.
    expected_non_planadeu = set(official_teams) - ({planadeu_name} if planadeu_name else set())
    missing_non_planadeu = expected_non_planadeu - set(used)
    inferred_eligible = (
        planadeu_name is not None
        and len(fixtures_list) == 7
        and len(set(used)) == 14
        and set(used).issubset(expected_non_planadeu)
        and len(missing_non_planadeu) == 1
        and bye_match is not None
    )
    if inferred_eligible:
        resting_team = _find_resting_team(full_text, team_lookup, planadeu_name)
        if resting_team in missing_non_planadeu:
            # The return-leg fixture reverses home/away; within the first leg,
            # alternate the provisional side to avoid a schedule with all Planadeu
            # fixtures at home or all away. The pending banner makes this inferred
            # orientation explicit until a verified source replaces it.
            first_leg_round = target_matchday if target_matchday <= 15 else target_matchday - 15
            planadeu_home = first_leg_round % 2 == 1
            if target_matchday > 15:
                planadeu_home = not planadeu_home
            anchor = min((item["kickoff"] for item in fixtures_list), default=datetime(2026, 8, 1, 12, 0))
            pending_fixture = {
                "home": planadeu_name if planadeu_home else resting_team,
                "away": resting_team if planadeu_home else planadeu_name,
                "kickoff": anchor.replace(hour=12, minute=0, second=0, microsecond=0),
                "kickoff_confirmed": False,
                "home_goals": None,
                "away_goals": None,
                "result_is_final": False,
                "is_played": False,
                "fixture_inferred": True,
                "source": f"{source_name} (emparejamiento inferido; pendiente de confirmar)",
            }
            fixtures_list.append(pending_fixture)
            return {
                "fixtures": fixtures_list,
                "bye": None,
                "source": source_name,
                "inferred_planadeu_fixture": True,
            }, None

    valid = (
        len(fixtures_list) == EXPECTED_FIXTURES
        and len(set(used)) == EXPECTED_TEAMS
        and set(used) == set(official_teams)
        and bye_match is None
        and any("planadeu" in norm(team) for team in used)
    )
    if not valid:
        recognized_teams = {
            team for alias, team in team_lookup.items()
            if alias and alias in visible_text
        }
        date_hits = len(SHORT_DATE_RE.findall(visible_text))
        missing_names = sorted(set(official_teams) - recognized_teams)
        round_contexts = sorted({
            item[2] for item in parser.candidates if item[2] is not None
        })
        candidate_samples = []
        for candidate_text, candidate_date, candidate_round in parser.candidates:
            candidate_norm = norm(candidate_text)
            found_teams = []
            for alias, team in team_lookup.items():
                if alias and alias in candidate_norm and team not in found_teams:
                    found_teams.append(team)
            if len(found_teams) >= 2:
                candidate_samples.append(
                    str(candidate_round) + "|" + str(candidate_date) + "|" +
                    ",".join(found_teams[:4]) + "|" + candidate_text[:100]
                )
            if len(candidate_samples) >= 5:
                break
        return None, (
            f"jornada incompleta desde {source_name}: {len(fixtures_list)} partidos "
            f"(se exigen {EXPECTED_FIXTURES}), {len(set(used))} equipos distintos "
            f"(se exigen {EXPECTED_TEAMS}), Planadeu="
            f"{'presente' if any('planadeu' in norm(team) for team in used) else 'ausente'}, "
            f"descanso={'detectado' if bye_match else 'no detectado'}; "
            f"nombres reconocidos={len(recognized_teams)}/{EXPECTED_TEAMS}, "
            f"nombres ausentes={','.join(missing_names)}, candidatos={len(parser.candidates)}, "
            f"jornadas_detectadas={round_contexts}, fechas visibles={date_hits}, muestras={candidate_samples}"
        )
    return {"fixtures": fixtures_list, "bye": None, "source": source_name}, None


def connect():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Falta el secreto DATABASE_URL en GitHub Actions.")
    return psycopg2.connect(database_url, connect_timeout=15, sslmode="require")


def require_import_schema(conn) -> None:
    """Refuse writes until the migration that protects internal fixtures is applied."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name='matches'"""
        )
        columns = {row[0] for row in cur.fetchall()}
    required = {"is_internal", "kickoff_confirmed"}
    missing = sorted(required - columns)
    if missing:
        raise RuntimeError(
            "No se habilita la escritura: falta aplicar la migración de partidos internos "
            f"(columnas ausentes: {', '.join(missing)})."
        )


def sync_round(conn, matchday: int, parsed, team_ids: dict, season_id: int):
    fixtures = parsed["fixtures"]
    expected_pairs = set()
    prepared = []
    if len(fixtures) != EXPECTED_FIXTURES:
        return 0, "jornada incompleta: se necesitan ocho partidos"
    for fixture in fixtures:
        home_id = team_ids.get(norm(fixture["home"]))
        away_id = team_ids.get(norm(fixture["away"]))
        if not home_id or not away_id or home_id == away_id:
            return 0, f"equipo sin correspondencia en Supabase: {fixture['home']} / {fixture['away']}"
        expected_pairs.add(frozenset((home_id, away_id)))
        prepared.append((home_id, away_id, fixture))

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT id, home_team_id, away_team_id, kickoff, home_goals, away_goals,
                      is_played, is_internal, kickoff_confirmed
               FROM matches WHERE season_id=%s AND matchday=%s""",
            (season_id, matchday),
        )
        existing = cur.fetchall()
        official_ids = set(team_ids.values())
        existing_official = [
            row for row in existing
            if row["home_team_id"] in official_ids
            and row["away_team_id"] in official_ids
            and not row["is_internal"]
        ]
        existing_pairs = {
            frozenset((row["home_team_id"], row["away_team_id"])) for row in existing_official
        }
        if not existing_pairs.issubset(expected_pairs):
            return 0, "conflicto con partidos oficiales ya guardados; no se modifica la jornada"

        written = 0
        for home_id, away_id, fixture in prepared:
            cur.execute(
                """SELECT id, home_team_id, away_team_id, kickoff, home_goals, away_goals,
                          is_played, is_internal, kickoff_confirmed
                   FROM matches
                   WHERE season_id=%s AND matchday=%s
                     AND ((home_team_id=%s AND away_team_id=%s)
                       OR (home_team_id=%s AND away_team_id=%s))
                   ORDER BY id LIMIT 1""",
                (season_id, matchday, home_id, away_id, away_id, home_id),
            )
            row = cur.fetchone()
            reversed_pair = bool(
                row and row["home_team_id"] == away_id and row["away_team_id"] == home_id
            )
            pairing_confirmed = bool(
                fixture.get("pairing_confirmed", not fixture.get("fixture_inferred", False))
            )
            # A bye-slot reconstruction is only a provisional fixture. Never let
            # it downgrade a previously confirmed kickoff or final result.
            if fixture.get("fixture_inferred") and row and (
                row["is_played"] or row["kickoff_confirmed"]
            ):
                continue

            # If a real source now confirms an inferred, unplayed pair, correct
            # its home/away orientation. Preserve orientation for any row that
            # already has a score/event history.
            correct_orientation = bool(
                reversed_pair
                and pairing_confirmed
                and row
                and not row["is_played"]
                and row["home_goals"] is None
                and row["away_goals"] is None
            )
            store_home_id = home_id if (not row or not reversed_pair or correct_orientation) else row["home_team_id"]
            store_away_id = away_id if (not row or not reversed_pair or correct_orientation) else row["away_team_id"]

            source_final = bool(
                fixture.get("result_is_final")
                and fixture["home_goals"] is not None
                and fixture["away_goals"] is not None
            )
            if source_final:
                hg, ag = fixture["home_goals"], fixture["away_goals"]
                if reversed_pair and not correct_orientation:
                    hg, ag = ag, hg
                is_played = True
            elif row:
                # A live/partial source cannot erase or overwrite a confirmed score.
                hg, ag = row["home_goals"], row["away_goals"]
                if reversed_pair and correct_orientation:
                    hg, ag = ag, hg
                is_played = bool(row["is_played"] and hg is not None and ag is not None)
            else:
                hg, ag, is_played = None, None, False

            source_kickoff = fixture["kickoff"]
            if fixture.get("kickoff_confirmed"):
                kickoff = source_kickoff
                kickoff_confirmed = True
            elif row and row["kickoff_confirmed"] and row["kickoff"].date() == source_kickoff.date():
                # Keep an already confirmed time if the source repeats the same date
                # but omits the clock; otherwise treat the new date as pending.
                kickoff = row["kickoff"]
                kickoff_confirmed = True
            else:
                kickoff = source_kickoff
                kickoff_confirmed = False

            if row:
                cur.execute(
                    """UPDATE matches SET home_team_id=%s, away_team_id=%s,
                       kickoff=%s, home_goals=%s, away_goals=%s,
                       is_played=%s, is_internal=FALSE, kickoff_confirmed=%s,
                       played_at=CASE WHEN %s THEN COALESCE(played_at, NOW()) ELSE played_at END
                       WHERE id=%s""",
                    (store_home_id, store_away_id, kickoff, hg, ag, is_played,
                     kickoff_confirmed, is_played, row["id"]),
                )
            else:
                cur.execute(
                    """INSERT INTO matches
                       (matchday, kickoff, home_goals, away_goals, is_played, season_id,
                        home_team_id, away_team_id, is_internal, kickoff_confirmed)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,FALSE,%s)""",
                    (matchday, kickoff, hg, ag, is_played, season_id,
                     store_home_id, store_away_id, kickoff_confirmed),
                )
            written += 1
    conn.commit()
    return written, None


def main():
    mode = "WRITE" if ENABLE_IMPORT else "DRY RUN (sin escrituras)"
    print(f"Planadeu sync | Juvenil C | Juvenil Segona Divisió Grup 29 | temporada {SEASON_NAME} | {mode}")
    conn = connect()
    total_written = 0
    verified = 0
    skipped = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if SEASON_ID_ENV.isdigit():
                cur.execute(
                    "SELECT id, name FROM seasons WHERE id=%s AND name=%s",
                    (int(SEASON_ID_ENV), SEASON_NAME),
                )
            else:
                cur.execute("SELECT id, name FROM seasons WHERE name=%s ORDER BY id", (SEASON_NAME,))
            seasons = cur.fetchall()
            if len(seasons) != 1:
                raise RuntimeError(
                    f"Se esperaba una única temporada {SEASON_NAME}; se encontraron {len(seasons)}. "
                    "No se escribe nada."
                )
            season = seasons[0]
            season_id = season["id"]
            cur.execute(
                """SELECT t.id, t.name FROM teams t
                   JOIN season_teams st ON st.team_id=t.id
                   WHERE st.season_id=%s
                   ORDER BY t.name""",
                (season_id,),
            )
            rows = cur.fetchall()

        if len(rows) != EXPECTED_TEAMS:
            raise RuntimeError(
                f"Se esperaban {EXPECTED_TEAMS} equipos asociados a {SEASON_NAME}; hay {len(rows)}. "
                "No se importa ninguna jornada."
            )
        official_teams = [row["name"] for row in rows]
        team_ids = {norm(row["name"]): row["id"] for row in rows}
        planadeu = [name for name in official_teams if "planadeu" in norm(name)]
        if len(planadeu) != 1:
            raise RuntimeError(
                f"Se esperaba exactamente un equipo Planadeu en la temporada y hay {len(planadeu)}. "
                "No se escribe nada."
            )
        print(f"Plantilla de base de datos verificada: {len(official_teams)} equipos, incluye {planadeu[0]}.")

        if ENABLE_IMPORT:
            require_import_schema(conn)
            print("Escrituras habilitadas por configuración explícita y esquema verificado.")
        else:
            print("Modo seguro: únicamente se inspeccionan fuentes; Supabase no se modifica.")

        # The public provider index starts at 5 for matchday 1.
        # Keep app round (1..30) separate from the source query index.
        for matchday in MATCHDAYS:
            attempts = []
            if CLUB_FIXTURES_URL:
                attempts.append(("Club feed", fetch_club_feed, True))
            attempts.extend([
                ("Futbuteo", lambda value=futbuteo_query_for_matchday(matchday): fetch_page(value), False),
                ("elFutbol", fetch_elfutbol_page, False),
            ])
            parsed = None
            last_error = None
            for source_name, fetcher, is_structured_feed in attempts:
                try:
                    source_payload = fetcher()
                    if is_structured_feed:
                        candidate, error = parse_club_feed(
                            source_payload, official_teams, matchday
                        )
                    else:
                        candidate, error = parse_round(
                            source_payload, official_teams, matchday, source_name
                        )
                    if error:
                        last_error = error
                        print(f"Jornada {matchday}: {source_name} rechazada — {error}")
                        continue
                    parsed = candidate
                    break
                except Exception as exc:
                    last_error = f"fuente no disponible ({type(exc).__name__})"
                    print(f"Jornada {matchday}: {source_name} no disponible ({type(exc).__name__}).")

            if parsed is None:
                skipped.append((matchday, last_error or "ninguna fuente válida"))
                continue

            verified += 1
            if not ENABLE_IMPORT:
                detail = (
                    "; incluye emparejamiento provisional de Planadeu inferido del descanso"
                    if parsed.get("inferred_planadeu_fixture") else ""
                )
                print(
                    f"Jornada {matchday}: VALIDADA en seco por {parsed['source']}; "
                    f"{len(parsed['fixtures'])} partidos, Planadeu incluido{detail}. Sin escrituras."
                )
                continue

            try:
                written, error = sync_round(conn, matchday, parsed, team_ids, season_id)
                if error:
                    conn.rollback()
                    skipped.append((matchday, error))
                    print(f"Jornada {matchday}: OMITIDA — {error}")
                    continue
                total_written += written
                print(
                    f"Jornada {matchday}: sincronizada desde {parsed['source']}; "
                    f"{written} partidos."
                )
            except Exception as exc:
                conn.rollback()
                reason = f"error seguro de sincronización ({type(exc).__name__})"
                skipped.append((matchday, reason))
                print(f"Jornada {matchday}: OMITIDA — {reason}")
            time.sleep(0.5)
    finally:
        conn.close()
        close_fetch_browser()

    print(
        f"RESUMEN: {verified} jornadas validadas; {total_written} partidos escritos; "
        f"{len(skipped)} jornadas no validadas. Modo: {mode}."
    )
    if skipped:
        print("Pendientes de revisión:")
        for matchday, reason in skipped:
            print(f"- Jornada {matchday}: {reason}")
    if verified == 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
