# Demo Mode

The hosted demo can run as a frontend-only Vercel app with no backend, no API keys, and no paid infrastructure.

## Purpose

Demo mode lets reviewers explore the product experience safely:

- guided discovery preview
- selecting and saving leads
- saved leads workspace
- filters and search
- detail panel
- local export
- English / Portuguese UI switching

The data is fictional sample data. It is not scraped from providers and does not require Google Places, CNPJA, or a backend database.

## Guided Searches

Demo mode intentionally supports curated searches instead of pretending every possible live search is available.

Portuguese / Brazil examples:

- `dentistas em São Paulo`
- `restaurantes em Campinas`
- `clínicas de estética no Rio de Janeiro`
- `materiais de construção em Belo Horizonte`

English / Europe examples:

- `dental clinics in Lisbon`
- `restaurants in Barcelona`
- `aesthetic clinics in London`
- `solar installers in Berlin`

Unsupported searches show a guided message instead of unrelated fake results. This keeps the demo honest while still letting reviewers explore the workflow.

## Enable Demo Mode

Set this environment variable in Vercel or `web/.env.local`:

```env
NEXT_PUBLIC_DEMO_MODE=true
```

When enabled, frontend API clients use `web/lib/demo/*` instead of the real backend proxy.

## Persistence

Demo interactions are stored in browser `localStorage`:

- saved demo leads
- demo import batches

This is intentional for the hosted demo. Each reviewer can interact with the app without changing shared backend data.

## Full Project Still Included

The repository still contains the full production-capable project:

- FastAPI backend
- Google Places discovery integration
- SQLite persistence
- CNPJ enrichment and review workflows
- backend export pipeline
- Docker/client deployment scripts

API keys are intentionally excluded and must be supplied through environment variables for real production mode.
