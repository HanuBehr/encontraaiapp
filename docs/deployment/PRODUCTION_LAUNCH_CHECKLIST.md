# Production Launch Checklist

Use this checklist for the first hosted production deployment.

## 1. Rotate And Restrict Google Key

Do this in Google Cloud before deploying with the current key.

- Create a new API key or rotate the existing exposed key.
- Enable only the APIs the app uses: `Places API (New)` and `Geocoding API`.
- Set application restrictions when the backend host has a stable egress IP. If the host does not provide one, keep strict API restrictions and low quota limits until a stable backend network is available.
- Set daily quota and billing alerts for Places and Geocoding.
- Put the key only in the backend host secret manager as `GOOGLE_API_KEY`.
- Do not add Google keys to Vercel or any `NEXT_PUBLIC_*` variable.

## 2. Deploy Backend

Use Render, Fly.io, Railway, or a VPS/Docker host. The backend must have persistent storage for SQLite and exports.

For Render, use the repository `render.yaml` blueprint and set `GOOGLE_API_KEY` in the Render dashboard when prompted.

Required runtime settings:

```env
APP_ENV=production
GOOGLE_API_KEY=replace-in-secret-manager
CNPJ_COMPANY_SEARCH_ENABLED=false
DATABASE_URL=sqlite:////app/data/app.db
EXPORT_DIR=/app/data/exports
SQLITE_JOURNAL_MODE=TRUNCATE
```

Required persistent paths:

- `/app/data`
- `/app/data/exports`

Container settings:

- Dockerfile: `Dockerfile.backend`
- Port: `8000`
- Health check path: `/health`

After deploy, verify:

```text
https://your-backend-host/health
```

Expected result: HTTP `200` with provider status showing Google configured.

## 3. Deploy Frontend

Use Vercel with the project root set to `web/`.

Set only this production environment variable in Vercel:

```env
BACKEND_URL=https://your-backend-host
```

Build settings:

- Install command: `npm install` or Vercel default
- Build command: `npm run build`
- Output: Next.js default/Vercel managed

Do not configure `GOOGLE_API_KEY`, `CNPJA_API_KEY`, or other provider secrets in Vercel.

## 4. Production Smoke Test

Run this from the deployed frontend URL.

- Open `/discovery` and confirm the page is styled.
- Confirm `Por termo` is visible and accepts up to `20`.
- Run a small Google discovery preview.
- Confirm preview results load and can be selected.
- Save selected leads.
- Open `/leads` and confirm saved leads appear.
- Export leads and download the generated file.
- Confirm CNPJ-heavy actions stay hidden while `CNPJ_COMPANY_SEARCH_ENABLED=false`.

## 5. Rollback Plan

If production fails after deploy:

- Roll Vercel back to the previous deployment.
- Roll the backend host back to the previous image/release.
- Keep the persistent disk mounted; do not delete `/app/data` or `/app/exports`.
- Check backend logs before retrying discovery because Google quota/errors can look like frontend failures.
