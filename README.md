# Encontra.ai

B2B prospecting is not slow because sales teams cannot sell. It is slow because the lead list is usually garbage.

Encontra.ai turns a market idea like `dental clinics in San Francisco` or `restaurants in New York` into a reviewed lead list ready for outreach. It handles discovery, duplicate prevention, contact enrichment, company-record evidence scoring, manual review, and spreadsheet export.

- Live demo: [https://encontraaiapp.vercel.app](https://encontraaiapp.vercel.app)
- No login required
- No API keys required for the demo
- Fictional sample data in demo mode

## Why This Exists

The expensive part of outbound sales often happens before the first call:

- searching Google manually
- copying companies into spreadsheets
- cleaning duplicate records
- checking whether a company has a usable website or contact channel
- guessing whether a company record belongs to the right business
- exporting a list that still needs another cleanup pass

Encontra.ai is the lead preparation layer before outreach. The goal is simple: spend less time building the list and more time talking to customers.

## Workflow

```text
Market search -> Discovery preview -> Dedupe -> Enrichment -> Company review -> Export
```

1. Search for companies by niche and location.
2. Preview provider results before saving anything.
3. Keep duplicates and already-saved companies out of the import.
4. Enrich saved leads with websites, domains, emails, phones, WhatsApp, Instagram, and quality signals.
5. Score and review uncertain company-record matches instead of silently assigning the wrong business entity.
6. Filter, assign, review, and export the final lead list.

## What Makes It Useful

- Preview-first discovery keeps bad provider results out of the workspace.
- Dedupe runs before import, so the lead list does not rot immediately.
- Enrichment is batch-oriented because manually checking websites does not scale.
- Company-record matching uses evidence across name, location, address, phone, domain, email, and category signals.
- Ambiguous company matches go to review instead of being treated as truth.
- Export rules prefer confirmed or approved company records.
- Demo mode runs without secrets, backend infrastructure, or paid provider calls.

## Engineering Decisions

- **FastAPI owns provider work.** Discovery, enrichment, registry lookup, scoring, and exports run server-side where secrets and long-running work belong.
- **Next.js owns the workspace.** The frontend is a workflow-heavy product surface with discovery, saved leads, review queues, filters, and localized UI.
- **The API proxy keeps secrets out of the browser.** Provider keys stay on the backend, not in `NEXT_PUBLIC_*` variables.
- **Provider integrations are adapters.** Google Places, geocoding, and optional registry providers are isolated behind service/provider modules.
- **Demo mode is deliberate.** The hosted demo swaps real backend calls for browser-local fixtures so the product can be reviewed instantly.
- **SQLite is intentional for local and pilot use.** The app is easy to run locally and inspect. Larger deployments should add managed database storage and migrations.
- **Docker is included for repeatable local deployment.** The app can run as a Dockerized frontend/backend pair with persistent local data.

## Architecture

```text
Browser workspace
  -> Next.js app and API proxy
  -> FastAPI backend
  -> SQLAlchemy / SQLite
  -> Discovery, enrichment, scoring, company review, export services
  -> Google Places / optional registry providers
```

The frontend owns interaction and stateful review flows. The backend owns provider calls, persistence, evidence scoring, enrichment, company-review workflows, and Excel export generation.

## Demo Vs Backend

| Mode | Purpose | Backend | API keys | Data |
| --- | --- | --- | --- | --- |
| Hosted demo | Public product review | No | No | Fictional browser-local fixtures |
| Local development | Full-stack development | FastAPI local process | Google key for real discovery | Local SQLite |
| Local Docker | Repeatable local deployment | Docker Compose | Google key for real discovery | Persistent `./data` |
| Backend-backed deployment | Real provider flow | Separate backend host | Backend secret manager | Persistent backend disk |

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
- Optional company-registry provider adapters
- Excel export pipeline
- Docker and Docker Compose
- Vercel frontend demo path
- Render backend blueprint
- Windows local deployment scripts

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

## Verification

The current codebase has backend service/API regression coverage and frontend build checks.

Backend:

```powershell
pytest
```

Frontend:

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

## Run The Demo Locally

The hosted demo does not require a backend. To run the frontend in demo mode locally:

```powershell
cd web
npm install
Copy-Item .env.example .env.local
```

Set this in `web/.env.local`:

```env
NEXT_PUBLIC_DEMO_MODE=true
```

Then run:

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Run The Full Stack Locally

Prerequisites:

- Python 3.12 or newer
- Node.js 20 or newer
- npm 10 or newer
- `GOOGLE_API_KEY` for real Google Places discovery

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

## Cross-Platform Docker Quick Start

macOS/Linux:

```bash
git clone https://github.com/HanuBehr/encontraaiapp.git
cd encontraaiapp
cp .env.example .env
docker compose up --build
```

Windows PowerShell:

```powershell
git clone https://github.com/HanuBehr/encontraaiapp.git
cd encontraaiapp
Copy-Item .env.example .env
docker compose up --build
```

Open:

- [http://localhost:3000](http://localhost:3000)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Local Windows Installer

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

## Production Hardening Roadmap

- Managed PostgreSQL with migrations and backups.
- Authentication, organization access control, and audit trails.
- Background job processing with retries, observability, and provider contract tests.

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

## Documentation

- [`docs/README.md`](docs/README.md)
- [`docs/DEMO_MODE.md`](docs/DEMO_MODE.md)
- [`docs/deployment/VERCEL_DEMO.md`](docs/deployment/VERCEL_DEMO.md)
- [`docs/deployment/VERCEL_BACKEND.md`](docs/deployment/VERCEL_BACKEND.md)
- [`docs/deployment/PRODUCTION_LAUNCH_CHECKLIST.md`](docs/deployment/PRODUCTION_LAUNCH_CHECKLIST.md)
- [`docs/client-install/README.md`](docs/client-install/README.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Current Scope

This is not a CRM and it is not campaign automation. It is the lead preparation layer before outreach.

Current focus:

- discovery
- enrichment
- duplicate control
- company review
- lead operations
- export

Not included yet:

- authentication
- billing
- campaign automation
- multi-tenant account management
- managed production database migrations

The backend uses SQLite for local deployment and small single-tenant/pilot deployments. Larger production environments should add managed database storage, migrations, authentication, and operational monitoring before broad rollout.
