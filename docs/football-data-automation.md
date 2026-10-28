# Automatic football data integration

## Current stage: source preflight only

The GitHub Actions workflow `Football source preflight` runs daily and can also be
started manually. It checks whether the official FCF competition page and the
complementary Futboteo page are reachable and still identify **Juvenil Segona
Divisió, Grup 29**. It uploads a JSON report as an Actions artifact.

**It intentionally does not write to PostgreSQL/Supabase.** A page returning
HTTP 200 is not enough to prove that all fixtures are complete or that a score
is final. This safety gate must pass before an importer is allowed to modify
matches.

## Sources

- Official FCF: `https://www.fcf.cat/resultats/2627/futbol-11/juvenil-segona-divisio/grup-29`
- Complementary schedule/results: `https://futbuteo.com/catalunya/resultados/juvenil-segona-divisio/grup-29/`
- Legacy research reference: `https://github.com/pauruiz/fcf`

The legacy repository documents Objective-C methods for results, standings and
match acts. Its implementation explicitly targets `http://m.fcf.cat/data/` and
was marked as working in January 2014. The current FCF website is available over
HTTPS, but the legacy API is not considered verified until a read-only request
returns valid JSON for a known group and its response schema is checked.

## Run locally

```bash
python scripts/fcf_sync.py
python -m unittest discover -s tests
```

Optional source URL overrides: `FUTBOTEO_URL` and `FCF_URL`.

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


## Validation and database safeguards added

- `scripts/football_import_validation.py` normalizes Catalan/Spanish accents and
  validates the expected 15-team, seven-fixture matchday shape, unique team
  identities, a single resting team, and final-score confirmation. It is a
  validation layer, not a source-page parser or a database writer.
- The `matches` model and migration add `is_internal` and
  `kickoff_confirmed`. The migration marks only the existing unplayed
  2026-2027 UD Can Trias–UE Planadeu midnight placeholder as internal and
  unconfirmed, if that exact row exists.
- Official standings and form calculation exclude records marked internal.

## Still required before enabling automated imports

The source pages could not be fetched reliably from this session, so the current
HTML structure and the legacy FCF JSON endpoint response have not been verified.
No production database migration was run. Do not merge/deploy until the migration
chain is confirmed, the tests pass in GitHub Actions, the real source adapter is
implemented against captured current HTML/JSON, and a dry-run report matches a
known official matchday. Database writes must remain disabled until then.
