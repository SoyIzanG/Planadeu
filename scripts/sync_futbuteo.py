#!/usr/bin/env python3
"""Conservative sync for the club-agreed Juvenil C, Grup 29 schedule.

Planadeu is part of the agreed 2026-2027 roster even if public listings omit it.
A round is importable only with all 16 teams and 8 fixtures, including Planadeu.
Public pages with 15 teams/7 fixtures and a bye are incomplete and are never
written. Writes are disabled unless ENABLE_FOOTBALL_IMPORT=true is set.
"""
from __future__ import annotations

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
ELFUTBOL_URL = os.getenv("ELFUTBOL_URL", "https://elfutbol.co/en/competitions/juvenil-segona-divisio/grup-29")
SEASON_NAME = "2026-2027"
SEASON_ID_ENV = os.getenv("SEASON_ID", "").strip()
ENABLE_IMPORT = os.getenv("ENABLE_FOOTBALL_IMPORT", "false").strip().lower() == "true"
EXPECTED_TEAMS = 16
EXPECTED_FIXTURES = 8
# Futbuteo's j=5 page is internal matchday 1, j=6 is matchday 2, etc.
J_VALUES = range(5, 35)
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
    "ue rubi": ["rubi ue"],
    "can trias": ["can trias ud"],
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
        "planadeu",
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
        candidate = tag.lower() in {"tr", "li"} or (
            tag.lower() in {"div", "article", "section"}
            and (CANDIDATE_CLASS_RE.search(classes or "") is not None or tag.lower() == "div")
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
                    except ValueError:
                        pass
            for node in self.stack:
                node["text"].append(data.strip())


_PLAYWRIGHT = None
_BROWSER = None
_BROWSER_PAGE = None
_ELFUTBOL_HTML = None


def _looks_like_challenge(html: str) -> bool:
    lower = (html or "").lower()
    visible = norm(re.sub(r"<[^>]+>", " ", html_lib.unescape(html or "")))
    explicit = (
        "necesitas tener activado javascript" in visible
        or "please enable javascript to continue" in visible
        or "checking your browser" in visible
        or "just a moment..." in visible
    )
    weak_challenge = (
        ("sessionstorage" in lower or "javascript" in visible)
        and not ("juvenil segona divisio" in visible and "grup 29" in visible)
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


def fetch_page(j_value: int) -> str:
    return _fetch_html(f"{BASE_URL}?j={j_value}")


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
    scores = []
    for match in SCORE_RE.finditer(cleaned):
        a, b = map(int, match.groups())
        if a <= 30 and b <= 30:
            scores.append((a, b))
    return scores[-1] if scores else (None, None)


def parse_round(html: str, official_teams: list[str], target_matchday: int, source_name: str):
    parser = CandidateParser()
    parser.feed(html)
    visible_html = html_lib.unescape(re.sub(r"<[^>]+>", " ", html))
    visible_text = norm(visible_html)
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
    bye_match = re.search(r"descans(?:a)?|rest(?:s|ing)?", full_text, re.I)
    used = [team for fixture in fixtures_list for team in (fixture["home"], fixture["away"])]
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
        date_hits = len(SHORT_DATE_RE.findall(visible_html))
        return None, (
            f"jornada incompleta desde {source_name}: {len(fixtures_list)} partidos "
            f"(se exigen {EXPECTED_FIXTURES}), {len(set(used))} equipos distintos "
            f"(se exigen {EXPECTED_TEAMS}), Planadeu="
            f"{'presente' if any('planadeu' in norm(team) for team in used) else 'ausente'}, "
            f"descanso={'detectado' if bye_match else 'no detectado'}; "
            f"nombres reconocidos={len(recognized_teams)}/{EXPECTED_TEAMS}, "
            f"fechas visibles={date_hits}"
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
            source_final = bool(
                fixture.get("result_is_final")
                and fixture["home_goals"] is not None
                and fixture["away_goals"] is not None
            )
            if source_final:
                hg, ag = fixture["home_goals"], fixture["away_goals"]
                if reversed_pair:
                    hg, ag = ag, hg
                is_played = True
            elif row:
                # A live/partial source cannot erase or overwrite a confirmed score.
                hg, ag = row["home_goals"], row["away_goals"]
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
                    """UPDATE matches SET kickoff=%s, home_goals=%s, away_goals=%s,
                       is_played=%s, is_internal=FALSE, kickoff_confirmed=%s,
                       played_at=CASE WHEN %s THEN COALESCE(played_at, NOW()) ELSE played_at END
                       WHERE id=%s""",
                    (kickoff, hg, ag, is_played, kickoff_confirmed, is_played, row["id"]),
                )
            else:
                cur.execute(
                    """INSERT INTO matches
                       (matchday, kickoff, home_goals, away_goals, is_played, season_id,
                        home_team_id, away_team_id, is_internal, kickoff_confirmed)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,FALSE,%s)""",
                    (matchday, kickoff, hg, ag, is_played, season_id,
                     home_id, away_id, kickoff_confirmed),
                )
            written += 1
    conn.commit()
    return written, None


def main():
    print(f"Planadeu sync | temporada {SEASON_NAME} | Futbuteo Grup 29")
    conn = connect()
    total_written = 0
    verified = 0
    skipped = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM seasons WHERE id=%s AND name=%s", (SEASON_ID, SEASON_NAME))
            season = cur.fetchone()
            if not season:
                raise RuntimeError(f"No se encuentra la temporada {SEASON_NAME} (id={SEASON_ID}).")
            cur.execute(
                """SELECT t.id, t.name FROM teams t
                   JOIN season_teams st ON st.team_id=t.id
                   WHERE st.season_id=%s AND t.name <> 'UE Planadeu'
                   ORDER BY t.name""",
                (SEASON_ID,),
            )
            rows = cur.fetchall()
        if len(rows) != 15:
            raise RuntimeError(f"Se esperaban 15 equipos oficiales en {SEASON_NAME}; hay {len(rows)}. No se escribe nada.")
        official_teams = [r["name"] for r in rows]
        team_ids = {norm(r["name"]): r["id"] for r in rows}
        # Build the parser map with canonical display names, while DB lookup is normalized.
        for j_value in J_VALUES:
            matchday = j_value - 4
            try:
                html = fetch_page(j_value)
                parsed, error = parse_round(html, official_teams)
                if error:
                    skipped.append((matchday, error))
                    print(f"Jornada {matchday}: OMITIDA — {error}")
                    continue
                written, error = sync_round(conn, matchday, parsed, team_ids)
                if error:
                    skipped.append((matchday, error))
                    print(f"Jornada {matchday}: OMITIDA — {error}")
                    continue
                verified += 1
                total_written += written
                print(f"Jornada {matchday}: verificada; descanso {parsed['bye']}; partidos sincronizados {written}.")
            except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError) as exc:
                conn.rollback()
                reason = f"fuente inaccesible o error de lectura ({type(exc).__name__})"
                skipped.append((matchday, reason))
                print(f"Jornada {matchday}: OMITIDA — {reason}")
            except Exception as exc:
                conn.rollback()
                # Do not print URLs, connection strings, or secrets.
                reason = f"error seguro de sincronización ({type(exc).__name__})"
                skipped.append((matchday, reason))
                print(f"Jornada {matchday}: OMITIDA — {reason}")
            time.sleep(0.7)
    finally:
        conn.close()

    print(f"RESUMEN: {verified} jornadas verificadas; {total_written} partidos insertados/actualizados; {len(skipped)} jornadas omitidas.")
    if skipped:
        print("Pendientes de revisión:")
        for matchday, reason in skipped:
            print(f"- Jornada {matchday}: {reason}")
    # Incomplete source access is a reportable state, not a fake successful sync.
    if verified == 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
