# Encontra.ai

Full-stack B2B lead discovery, enrichment, review, and export workspace.

Encontra.ai turns niche-and-location business searches into structured lead lists. It includes discovery previews, duplicate prevention, lead import, contact enrichment, CNPJ matching, manual review for uncertain matches, and spreadsheet export.

## Live Demo

- Demo: [https://encontraaiapp.vercel.app](https://encontraaiapp.vercel.app)
- Mode: frontend-only Vercel deployment
- Data: fictional sample companies and browser-local saved leads
- Requirements: no login, backend, or API keys

The hosted demo is intentionally scoped to curated search scenarios so the workflow can be reviewed without paid provider access. The backend-backed app in this repository supports real provider discovery when configured with private API keys.

## Highlights

- Search companies by niche, city, region, or coordinates
- Preview results before saving leads
- Prevent duplicates and detect already-saved companies
- Enrich leads with contacts, domains, profiles, and quality signals
- Resolve CNPJ candidates with scoring and manual review
- Filter, assign, review, and export lead lists
- Run as a hosted demo, local Docker deployment, or backend-backed app
- Bilingual interface: Portuguese and English

## Tech Stack

Backend:

- Python
- FastAPI
- SQLAlchemy
- SQLite
- pytest

Frontend:

- Next.js
- React
- TypeScript
- Tailwind CSS

Integrations and deployment:

- Google Places discovery and geocoding
- Optional CNPJ provider adapters
- Excel export pipeline
- Docker and Docker Compose
- Vercel frontend demo path
- Render backend blueprint
- Windows local deployment scripts

## Architecture

```text
Next.js frontend
  -> API proxy
  -> FastAPI backend
  -> SQLite + enrichment services + export service
  -> Google Places / optional CNPJ providers
```

The frontend owns the product workspace and user interactions. The backend owns provider calls, persistence, scoring, enrichment, CNPJ workflows, and export generation. Demo mode swaps backend API calls for browser-local fixtures.

## Product Workflow

1. Search for businesses by segment and location.
2. Review the discovery preview before importing anything.
3. Save selected companies into the leads workspace.
4. Enrich and score leads using available public/provider data.
5. Review uncertain CNPJ matches before approval.
6. Filter, assign, and export clean lead lists.

## CNPJ Resolution

CNPJ matching is designed to reduce bad assignments rather than silently guessing.

The workflow can combine:

- CNPJ extraction from company websites
- public CNPJ validation
- optional commercial provider search
- evidence scoring across names, city/state, CEP, address, phone, domain/email, and category signals
- manual review for ambiguous candidates
- export rules that prefer confirmed or approved CNPJs

## Prerequisites

Local development:

- Python 3.12 or newer
- Node.js 20 or newer
- npm 10 or newer

Docker deployment:

- Docker Desktop or Docker Engine with Compose support

Provider-backed discovery:

- `GOOGLE_API_KEY` for Google Places and Geocoding
- CNPJ provider keys only when optional CNPJ enrichment/search is enabled

## Getting Started

### Hosted Demo Frontend

Use Vercel with the project root set to `web` and this environment variable:

```env
NEXT_PUBLIC_DEMO_MODE=true
```

Do not set `BACKEND_URL` or provider API keys for the hosted demo.

See [`docs/deployment/VERCEL_DEMO.md`](docs/deployment/VERCEL_DEMO.md).

### Local Development

Backend:

```powershell
git clone https://github.com/HanuBehr/encontraaiapp.git
cd encontraaiapp

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\init_local_db.py
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --log-level info
```

Frontend:

```powershell
cd web
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open:

- [http://localhost:3000](http://localhost:3000)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Real discovery requires `GOOGLE_API_KEY` in `.env`. Without it, use hosted demo mode or frontend demo mode.

### Local Docker Deployment

For a local Windows Docker installation:

```powershell
git clone https://github.com/HanuBehr/encontraaiapp.git
cd encontraaiapp

.\scripts\client_install.ps1
notepad .env
.\scripts\client_start.ps1
```

Then open [http://localhost:3000](http://localhost:3000).

See [`docs/client-install/README.md`](docs/client-install/README.md) for the full installation guide.

## Environment

Templates:

- [`.env.example`](.env.example)
- [`web/.env.example`](web/.env.example)
- [`deploy/client/.env.client.example`](deploy/client/.env.client.example)

Common variables:

- `GOOGLE_API_KEY`
- `DATABASE_URL`
- `EXPORT_DIR`
- `BACKEND_URL`
- `NEXT_PUBLIC_DEMO_MODE`
- `CNPJ_LOOKUP_PROVIDER`
- `CNPJ_COMPANY_SEARCH_ENABLED`
- `CNPJ_COMPANY_SEARCH_PROVIDER`
- `CNPJA_API_KEY` when paid CNPJ enrichment/search is enabled

Secrets must stay in local environment files or deployment secret managers. They should not be committed.

## Repository Structure

```text
app/       FastAPI backend, models, services, providers, exports
web/       Next.js frontend, demo mode, API proxy, UI components
scripts/   Local operations, setup, diagnostics, and packaging helpers
tests/     Backend regression and service tests
docs/      Demo, deployment, installation, and operations guides
deploy/    Deployment-specific environment templates
```

Runtime folders such as `data/`, `exports/`, `backups/`, `dist/`, `.venv/`, `.next/`, and `node_modules/` are intentionally ignored.

## Documentation

- [`docs/README.md`](docs/README.md)
- [`docs/DEMO_MODE.md`](docs/DEMO_MODE.md)
- [`docs/deployment/VERCEL_DEMO.md`](docs/deployment/VERCEL_DEMO.md)
- [`docs/deployment/VERCEL_BACKEND.md`](docs/deployment/VERCEL_BACKEND.md)
- [`docs/deployment/PRODUCTION_LAUNCH_CHECKLIST.md`](docs/deployment/PRODUCTION_LAUNCH_CHECKLIST.md)
- [`docs/client-install/README.md`](docs/client-install/README.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Verification

Backend tests:

```powershell
pytest
```

Frontend checks:

```powershell
cd web
npm run typecheck
npm test
npm run build
```

Demo build:

```powershell
cd web
cmd.exe /c "set NEXT_PUBLIC_DEMO_MODE=true&& npm run build"
```

## Current Scope

Encontra.ai is focused on discovery, enrichment, CNPJ review, lead operations, and export. It does not currently include authentication, billing, campaign automation, or multi-tenant account management.

The backend uses SQLite for local deployment and small single-tenant/pilot deployments. Larger production environments should add managed database storage, migrations, authentication, and operational monitoring before broad rollout.
