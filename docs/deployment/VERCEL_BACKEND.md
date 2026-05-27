# Vercel + Backend Deployment

This app should not be deployed as Vercel-only in its current architecture.

Use Vercel for the Next.js frontend and a separate backend host for FastAPI with persistent storage.

## Why Not Vercel-Only

- The frontend is a Next.js app and fits Vercel well.
- The backend is FastAPI and uses long-running API work for discovery/enrichment.
- SQLite and export files require persistent storage.
- Vercel serverless storage is ephemeral and should not hold `app.db` or generated exports.

## Recommended First Production Shape

- Frontend: Vercel project rooted at `web/`
- Backend: Render, Fly.io, Railway, or a VPS running Docker
- Database: SQLite on persistent disk for first production pass
- Exports: persistent disk on the backend host

## Frontend Environment

Create the Vercel project with `web/` as the root directory.

Set this in Vercel only:

```env
BACKEND_URL=https://your-backend-host.example.com
```

Do not set provider secrets in Vercel frontend env vars. Do not create any `NEXT_PUBLIC_*` API-key variable.

The frontend calls `/api/backend/*`; the Next.js route proxies those requests to `BACKEND_URL` server-side.

## Backend Environment

Set provider secrets only on the backend host:

```env
APP_ENV=production
GOOGLE_API_KEY=
CNPJ_COMPANY_SEARCH_ENABLED=false
DATABASE_URL=sqlite:////app/data/app.db
EXPORT_DIR=/app/exports
SQLITE_JOURNAL_MODE=TRUNCATE
```

Fill `GOOGLE_API_KEY` in the backend host secret manager, not in Git.

CNPJ enrichment is optional. Enable it only after adding a provider key:

```env
CNPJ_COMPANY_SEARCH_ENABLED=true
CNPJ_COMPANY_SEARCH_PROVIDER=cnpja_commercial
CNPJA_API_KEY=
```

Fill `CNPJA_API_KEY` only in the backend host secret manager.

## Secret Safety Rules

- Never commit `.env`, `.env.local`, database files, exports, or backups.
- Keep `GOOGLE_API_KEY` backend-only.
- Restrict the Google key by allowed APIs, quota, and billing limits.
- Rotate any key that was shared outside the secret manager.
- Run a tracked-file secret scan before pushing deploy changes.

## Pre-Deploy Verification

Run locally before deploying:

```powershell
.\.venv\Scripts\python.exe -m pytest
cd web
npm run typecheck
npm run build
```

Then verify backend deployment:

- `/health` returns `200`
- `/docs` is reachable only if you intend to expose it
- Discovery works with a small Google Places search
- Leads can be saved and exported

For the first production launch, follow the step-by-step checklist in [`PRODUCTION_LAUNCH_CHECKLIST.md`](PRODUCTION_LAUNCH_CHECKLIST.md).
