# Changelog

## v0.1.0 - Public engineering case study

- Documented the Next.js/FastAPI architecture, provider boundaries, demo mode and backend-backed deployment path.
- Added CI coverage for backend pytest, frontend typecheck, frontend tests and demo production build.
- Added an explicit database-recorded job abstraction for provider-heavy batch enrichment operations with idempotent job keys, bounded retries, job state and correlation IDs.
- Added structured operational logging for discovery, preview enrichment, dedupe, assignment, export and job attempts.
- Preserved the public demo, fictional demo data and current product scope.

Verification:

- `python -m pytest`
- `cd web && npm run typecheck`
- `cd web && npm test`
- `cd web && NEXT_PUBLIC_DEMO_MODE=true npm run build`
- Docker Compose configuration validation

Known limitations:

- Authentication, billing, campaign automation and full multi-tenant account management are not completed in this public scope.
- SQLite is the default for local and pilot deployment; production deployments should add managed PostgreSQL, migrations, backups and operational monitoring.
- Public demo data is fictional and browser-session scoped. Commercial implementations and client data remain private.
