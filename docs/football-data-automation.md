# Automatic football data integration

## Current stage: read-only FCF API adapter

The GitHub Actions workflow `Football source preflight` runs daily and on demand.
It now calls the legacy FCF results API contract recovered from
`pauruiz/fcf`: `POST https://m.fcf.cat/data/json_resultados.php` with
`id_grupo` and optional `jornada`. The adapter parses JSON and emits a
structural report; it does not write to PostgreSQL/Supabase.

The API was documented by a project last updated in 2014. The endpoint and its
current response format still need to pass a live request before this can be
considered operational. The public competition is Juvenil C, Grup 29. The script does not guess that
`29` is the historical API's internal `id_grupo`; set `FCF_GROUP_ID` only when
that internal identifier is verified. The agreed group selection is not rejected
merely because Planadeu is absent from a public listing.

## Competition context supplied by the club (2026-2027)

The target is **Juvenil C, Juvenil Segona Divisió, Grup 29**. The club has
explained that Planadeu is not displayed in the public listing because of an
administrative/payment issue, while an agreement exists for the team to
participate in this group. Therefore, the absence of Planadeu from a public
third-party listing must **not** be used to redirect the importer to Grup 32 or
to reject Grup 29 as the intended competition.

The importer must still distinguish the public competition number `29` from
the legacy API's internal `id_grupo`. It will only query a verified internal
ID (or a confirmed modern FCF competition/group ID), and must validate returned
fixtures against the agreed Juvenil C / Grup 29 schedule. Do not require the
public listing to contain Planadeu as the sole group-selection test.

## Sources

- Official FCF results page: `https://www.fcf.cat/resultats/2627/futbol-11/juvenil-segona-divisio/grup-29`
- Legacy FCF API reference: `https://github.com/pauruiz/fcf`
- Complementary results: `https://futbuteo.com/catalunya/resultados/juvenil-segona-divisio/grup-29/`
- Secondary provider: `https://elfutbol.co/en/competitions/juvenil-segona-divisio/grup-29?results=all&season=2627&tab=results`
- Optional club-owned JSON feed: configured by `CLUB_FIXTURES_URL` (recommended while public listings omit the agreed team).

Futbuteo's server response may be a JavaScript/cookie challenge. That source is
secondary and its challenge must not override a verified official FCF response.

## FCF access blocked from GitHub-hosted runners

The workflow now supports a self-hosted GitHub Actions runner. Verified tests
show that both direct HTTP requests and Chromium running on a GitHub-hosted
runner receive an AWS/CloudFront-style `403 Request blocked` from the FCF API.
This is not a missing query parameter, nor something that can be fixed by
retrying or changing the browser User-Agent.

For the reliable path, register a GitHub Actions runner on a club-controlled
Linux machine or server that can open the public FCF competition pages from its
normal network. Then set repository variable `FCF_RUNNER_LABELS` to the JSON
array `["self-hosted","linux","x64"]` (adjust labels to match the registered
runner). The workflow keeps the Chromium fallback for that runner. Do not use a
third-party proxy to evade the FCF block; obtain an approved API/feed or run the
job from an authorized network.

The hosted runner is now pinned to Ubuntu 24.04 because Playwright 1.55 does
not support the newer hosted Ubuntu 26.04 image. A self-hosted runner is still
available through `FCF_RUNNER_LABELS`. Even when a source page is reachable,
a page listing only 15 teams, seven matches and a bye is rejected for this
club-agreed 16-team, eight-match schedule.

## GitHub Actions configuration

Set repository variable `FCF_GROUP_ID` to the **internal group code returned by
the FCF system**, not the public group number, once verified. Optionally set
`FCF_MATCHDAY` to a round number (1-30) to validate one round; if omitted, the
API response is summarized without asserting that it is a complete matchday.
`FCF_GROUP_ID` is only for the read-only legacy FCF adapter. The daily sync
supports an approved, club-owned JSON feed (see below). All database writes are
disabled by default and require `ENABLE_FOOTBALL_IMPORT=true`; writes also
refuse to run until the `is_internal` and `kickoff_confirmed` migration has
been applied.

## Run locally

```bash
FCF_GROUP_ID=<verified-internal-code> python scripts/fcf_sync.py
python -m unittest discover -s tests -v
```

Optional settings: `FCF_API_BASE`, `FCF_MATCHDAY`, and `FUTBOTEO_URL`.

## Required safeguards before database writes

1. Verify season and group identity, source freshness, and a complete matchday.
2. Match source team names to existing database teams using explicit aliases;
   never create teams or matches from an ambiguous name.
3. Keep official fixtures/results separate from any internal Planadeu fixture.
4. Never infer a kickoff time. Missing date/time must remain pending in the UI,
   not be encoded as midnight.
5. Update only confirmed final scores; do not derive player events or acta data
   from the score alone.
6. Make writes transactional and idempotent; keep a per-run audit report.
7. Test that internal fixtures never affect official standings.
8. Keep all database credentials in GitHub Actions secrets; never print them.

## Approved JSON feed contract (recommended alternative)

Set repository variable `CLUB_FIXTURES_URL` to a club-owned HTTPS endpoint or
an approved export URL that returns UTF-8 JSON. If the endpoint requires a
Bearer token, store it as secret `CLUB_FIXTURES_TOKEN`. The feed must include
the exact database team names and must not use another Planadeu squad as an
alias for Juvenil C.

Example shape (illustrative only; the team list and fixture values below are
not real match data):

```json
{
  "competition": "Juvenil Segona Divisió Grup 29",
  "season": "2026-2027",
  "teams": ["<exact database team 1>", "... exactly 16 database team names ..."],
  "fixtures": [
    {
      "matchday": 1,
      "home": "<exact home team name>",
      "away": "<exact away team name>",
      "date": "2026-10-31",
      "time": "12:00",
      "home_goals": null,
      "away_goals": null,
      "result_is_final": false
    }
  ]
}
```

Each round must provide eight fixtures, and all 16 declared teams must play
exactly once in that round. Dates are required. If a clock time is unknown,
omit `time`; the app stores a noon placeholder with `kickoff_confirmed=false`
so it is not presented as the real kickoff. A score is used only when
`result_is_final` is `true` and both goal values are valid integers. The
feed can contain the whole season; each fixture must carry `matchday`.

## Validation and database safeguards already added

- `scripts/football_import_validation.py` validates the club-agreed 16-team,
  eight-fixture matchday shape, unique team identities, complete team coverage
  and final-score confirmation. A bye is not expected for this 16-team roster.
- `scripts/sync_futbuteo.py` tries the optional club-owned JSON feed first,
  followed by Futbuteo and elFutbol. It validates group, season, exact roster,
  all eight fixtures, confirmed times, and explicitly final scores. It never
  imports a public 15-team round that omits Planadeu.
- The `matches` model and migration add `is_internal` and
  `kickoff_confirmed`. The migration marks only the existing unplayed
  2026-2027 UD Can Trias–UE Planadeu midnight placeholder as internal and
  unconfirmed, if that exact row exists.
- Official standings and form calculation exclude records marked internal.

## Still required before enabling automated imports

The current FCF API routes return HTTP 403 from GitHub-hosted Actions, and the
public secondary listings currently expose only 15 teams/seven matches in
Grup 29, without Planadeu. Therefore they fail validation as designed. The
internal FCF group code is not known; the Supabase migration has not been run.
A valid club-owned JSON feed or an authorised source that actually returns the
agreed 16-team schedule is still required before the real feed can be imported.
Keep database writes disabled until that source and the migration are verified.
