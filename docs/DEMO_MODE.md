# Demo Mode

The hosted demo can run as a frontend-only Vercel app with no backend or API keys.

## Purpose

Demo mode lets reviewers explore the product experience safely:

- guided discovery preview
- selecting and saving leads
- saved leads workspace that starts empty
- filters and search
- detail panel
- local export
- English / Portuguese UI switching

The data is fictional sample data. It is not scraped from providers and does not require Google Places, CNPJA, or a backend database.

## Guided Searches

Demo mode supports curated searches instead of open-ended live provider queries.

Each guided search returns 20 fictional candidates with mixed website, email, phone, WhatsApp, and Instagram coverage.

Portuguese examples are Brazil-only:

- `clínicas odontológicas em São Paulo`
- `restaurantes em Campinas`
- `clínicas de estética no Rio de Janeiro`
- `empresas de logística em Belo Horizonte`
- `materiais de construção em Curitiba`
- `academias em Porto Alegre`

English examples use major international cities:

- `dental clinics in San Francisco`
- `restaurants in New York`
- `aesthetic clinics in London`
- `solar installers in Berlin`
- `logistics companies in Amsterdam`
- `boutique hotels in Melbourne`
- `marketing agencies in Toronto`
- `fitness studios in Dublin`

Unsupported searches show a guided message instead of unrelated sample results.

## Enable Demo Mode

Set this environment variable in Vercel or `web/.env.local`:

```env
NEXT_PUBLIC_DEMO_MODE=true
```

When enabled, frontend API clients use `web/lib/demo/*` instead of the real backend proxy.

## Persistence

Demo interactions are stored in browser `sessionStorage`:

- saved demo leads
- demo import batches
- language choice for the current tab/session

This is intentional for the hosted demo. Each new visit starts in English with an empty saved-leads workspace, while the current tab keeps saved leads and language choice as reviewers move between pages. English and Portuguese demo workspaces are stored separately so saved leads do not cross languages.

## Backend-Backed App

The repository also includes the backend-backed app:

- FastAPI backend
- Google Places discovery integration
- SQLite persistence
- CNPJ enrichment and review workflows
- backend export pipeline
- Docker deployment scripts

API keys are intentionally excluded and must be supplied through environment variables for provider-backed discovery.
