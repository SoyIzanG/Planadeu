#!/usr/bin/env python3
"""Conservative daily sync for Juvenil Segona Divisió, Grup 29.

Only writes a matchday after the source page yields all seven official fixtures,
all 15 official teams exactly once (14 playing + one bye), and a date for every
fixture. Unparseable or incomplete pages are reported and left untouched.
"""
from __future__ import annotations

import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg2
from psycopg2.extras import RealDictCursor

BASE_URL = "https://futbuteo.com/catalunya/resultados/juvenil-segona-divisio/grup-29/"
SEASON_NAME = "2026-2027"
SEASON_ID = int(os.getenv("SEASON_ID", "1"))
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
}


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


class CandidateParser(HTMLParser):
    """Collect likely fixture rows/cards without assuming one specific HTML layout."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.candidates = []
        self.full_text = []
        self.current_date = None
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
        node = {"tag": tag.lower(), "attrs": attrs, "text": [], "date_context": self.current_date} if candidate else None
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
                        self.candidates.append((text, node["date_context"]))
                break

    def handle_data(self, data):
        if data.strip():
            self.full_text.append(data.strip())
            self.recent_text = (self.recent_text + " " + data.strip())[-180:]
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


def fetch_page(j_value: int) -> str:
    url = f"{BASE_URL}?j={j_value}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return response.read().decode("utf-8", errors="replace")


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


def parse_round(html: str, official_teams: list[str]):
    parser = CandidateParser()
    parser.feed(html)
    team_lookup = {norm(team): team for team in official_teams}
    for team in official_teams:
        for canonical_key, aliases in TEAM_ALIASES.items():
            if norm(team) == canonical_key:
                for alias in aliases:
                    team_lookup[norm(alias)] = team
    fixtures = {}
    for candidate, date_context in parser.candidates:
        candidate_norm = norm(candidate)
        found = [team for key, team in team_lookup.items() if key and key in candidate_norm]
        # A fixture card must mention exactly two different official clubs.
        unique = list(dict.fromkeys(found))
        if len(unique) != 2:
            continue
        kickoff = parse_date(candidate)
        if kickoff is None and date_context is not None:
            clock_match = TIME_RE.search(candidate)
            if clock_match:
                hour, minute = map(int, clock_match.groups())
                kickoff = datetime(date_context.year, date_context.month, date_context.day, hour, minute)
            else:
                # Date is known but no kickoff time is shown; keep a neutral local noon.
                kickoff = datetime(date_context.year, date_context.month, date_context.day, 12, 0)
        if kickoff is None:
            continue
        hg, ag = parse_score(candidate, kickoff)
        key = frozenset(unique)
        fixtures[key] = {
            "home": unique[0], "away": unique[1], "kickoff": kickoff,
            "home_goals": hg, "away_goals": ag,
            "is_played": hg is not None and ag is not None,
        }

    # Deduplicate nested containers; accept only the exact 7 official fixtures.
    fixtures_list = list(fixtures.values())
    full_text = " ".join(parser.full_text)
    bye = None
    # Futbuteo labels the resting club "Descans" (Catalan), often immediately
    # followed by its abbreviated club name rather than "Descansa: Team".
    bye_match = re.search(r"\bdescans(?:a)?\b", full_text, re.I)
    if bye_match:
        bye_tail = norm(full_text[bye_match.end():bye_match.end() + 220])
        possible = []
        for alias, team in team_lookup.items():
            position = bye_tail.find(alias)
            if position >= 0:
                possible.append((position, team))
        if possible:
            earliest = min(position for position, _ in possible)
            nearest = list(dict.fromkeys(team for position, team in possible if position == earliest))
            if len(nearest) == 1:
                bye = nearest[0]

    used = [team for f in fixtures_list for team in (f["home"], f["away"])]
    valid = (
        len(fixtures_list) == 7
        and len(set(used)) == 14
        and set(used).issubset(set(official_teams))
        and bye in set(official_teams)
        and bye not in set(used)
        and set(used) | {bye} == set(official_teams)
    )
    if not valid:
        return None, (
            f"validación incompleta: {len(fixtures_list)} partidos candidatos, "
            f"{len(set(used))} equipos distintos, descanso={'detectado' if bye else 'no detectado'}"
        )
    return {"fixtures": fixtures_list, "bye": bye}, None


def connect():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Falta el secreto DATABASE_URL en GitHub Actions.")
    return psycopg2.connect(database_url, connect_timeout=15, sslmode="require")


def sync_round(conn, matchday: int, parsed, team_ids: dict):
    fixtures = parsed["fixtures"]
    expected_pairs = set()
    prepared = []
    for fixture in fixtures:
        home_id = team_ids.get(norm(fixture["home"]))
        away_id = team_ids.get(norm(fixture["away"]))
        if not home_id or not away_id or home_id == away_id:
            return 0, f"equipo sin correspondencia en Supabase: {fixture['home']} / {fixture['away']}"
        expected_pairs.add(frozenset((home_id, away_id)))
        prepared.append((home_id, away_id, fixture))

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT id, home_team_id, away_team_id, kickoff, home_goals, away_goals, is_played
               FROM matches WHERE season_id=%s AND matchday=%s""",
            (SEASON_ID, matchday),
        )
        existing = cur.fetchall()
        official_ids = set(team_ids.values())
        existing_official = [
            row for row in existing
            if row["home_team_id"] in official_ids and row["away_team_id"] in official_ids
        ]
        existing_pairs = {
            frozenset((row["home_team_id"], row["away_team_id"])) for row in existing_official
        }
        if not existing_pairs.issubset(expected_pairs):
            return 0, "conflicto con partidos oficiales ya guardados; no se modifica la jornada"

        written = 0
        for home_id, away_id, fixture in prepared:
            cur.execute(
                """SELECT id, home_team_id, away_team_id, kickoff, home_goals, away_goals, is_played
                   FROM matches
                   WHERE season_id=%s AND matchday=%s
                     AND ((home_team_id=%s AND away_team_id=%s)
                       OR (home_team_id=%s AND away_team_id=%s))
                   ORDER BY id LIMIT 1""",
                (SEASON_ID, matchday, home_id, away_id, away_id, home_id),
            )
            row = cur.fetchone()
            hg, ag = fixture["home_goals"], fixture["away_goals"]
            reversed_pair = row and row["home_team_id"] == away_id and row["away_team_id"] == home_id
            if reversed_pair:
                hg, ag = ag, hg
            if row:
                # Never downgrade a known final score to an unknown score.
                if hg is None or ag is None:
                    hg = row["home_goals"]
                    ag = row["away_goals"]
                is_played = hg is not None and ag is not None
                cur.execute(
                    """UPDATE matches SET kickoff=%s, home_goals=%s, away_goals=%s,
                       is_played=%s, played_at=CASE WHEN %s THEN COALESCE(played_at, NOW()) ELSE played_at END
                       WHERE id=%s""",
                    (fixture["kickoff"], hg, ag, is_played, is_played, row["id"]),
                )
            else:
                cur.execute(
                    """INSERT INTO matches
                       (matchday, kickoff, home_goals, away_goals, is_played, season_id, home_team_id, away_team_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (matchday, fixture["kickoff"], hg, ag, hg is not None and ag is not None,
                     SEASON_ID, home_id, away_id),
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
