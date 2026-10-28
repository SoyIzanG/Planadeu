# Automatic football data integration

## Current stage: read-only FCF API adapter

The GitHub Actions workflow `Football source preflight` runs daily and on demand.
It now calls the legacy FCF results API contract recovered from
`pauruiz/fcf`: `POST https://m.fcf.cat/data/json_resultados.php` with
`id_grupo` and optional `jornada`. The adapter parses JSON and emits a
structural report; it does not write to PostgreSQL/Supabase.

The API was documented by a project last updated in 2014. The endpoint and its
current response format still need to pass a live request before this can be
considered operational. If `FCF_GROUP_ID` is not configured, the preflight probes
`29` only as a candidate and rejects it unless returned rows contain both known
teams (Planadeu and Can Trias). This is a discovery check, not proof that 29 is
the internal code for all future requests.

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

Futbuteo's server response may be a JavaScript/cookie challenge. That source is
secondary and its challenge must not override a verified official FCF response.

## GitHub Actions configuration

Set repository variable `FCF_GROUP_ID` to the **internal group code returned by
the FCF system**, not the public group number, once verified. Optionally set
`FCF_MATCHDAY` to a round number (1-30) to validate one round; if omitted, the
API response is summarized without asserting that it is a complete matchday.
The current script accepts no credentials and performs no writes.

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

## Validation and database safeguards already added

- `scripts/football_import_validation.py` normalizes Catalan/Spanish accents and
  validates the expected 15-team, seven-fixture matchday shape, unique team
  identities, a single resting team, and final-score confirmation.
- The `matches` model and migration add `is_internal` and
  `kickoff_confirmed`. The migration marks only the existing unplayed
  2026-2027 UD Can Trias–UE Planadeu midnight placeholder as internal and
  unconfirmed, if that exact row exists.
- Official standings and form calculation exclude records marked internal.

## Still required before enabling automated imports

The live legacy API has not yet been confirmed to respond with current JSON, and
the internal FCF group code is not known. The current FCF API routes return HTTP 403 from GitHub Actions. The Supabase migration has not been
run. Confirm the repository's migration chain, test a dry-run against a known
official matchday, and keep database writes disabled until that succeeds.
