# Vercel Demo Deployment

Use this for the free recruiter demo.

## 1. Import Project

In Vercel, import the GitHub repository:

```text
HanuBehr/encontraaiapp
```

Set root directory:

```text
web
```

## 2. Environment Variables

Set only:

```env
NEXT_PUBLIC_DEMO_MODE=true
```

Do not set these for the demo:

```env
BACKEND_URL
GOOGLE_API_KEY
CNPJA_API_KEY
```

## 3. Build

Use the normal frontend build:

```bash
npm run build
```

## 4. Smoke Test

Open the deployed Vercel URL and test:

- `/settings`
- `/discovery`
- `/leads`
- language switching
- guided demo searches
- saving demo leads from discovery
- exporting leads

The app should show a badge:

```text
Demo mode: sample data
```

## Notes

This deployment intentionally does not run the FastAPI backend. It is a frontend-only product demo using fictional browser-local data.

The demo supports curated fictional searches only. The full repository includes the backend implementation for real provider-backed searches when private API keys are configured.
