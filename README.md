# Encontra.ai Lead Discovery and Operations

Encontra.ai is a lead discovery and operations platform for researching public businesses, enriching contact data, reviewing lead quality, and managing assignment workflows.

## Architecture

- `web/` is the primary V2 product: a Next.js 15 / React 19 workspace for discovery and lead operations.
- `app/` contains the FastAPI backend, SQLAlchemy models, repositories, and services.
- `streamlit_app.py` remains available as a legacy internal workspace, but it is not the main UI.

## What is implemented

- Google Places discovery ingestion with `ImportBatch` tracking
- append-only raw discovery history
- public-site enrichment with provenance-preserving contact evidence
- V2 discovery and lead operations workspaces in Next.js
- lead review API and legacy internal Streamlit workspace
- deduplication and canonical merge logic
- lead scoring with stored reasoning
- assignment regions, market taxonomy, and validation tooling
- Excel export with `Leads`, `Outreach_Log`, `Templates`, `Settings`, and `Metadata`
- pytest coverage for normalization, enrichment, dedupe, scoring, assignment, export, and API contracts

## Stack

- Python 3.11+
- FastAPI
- Next.js 15
- React 19
- TypeScript
- SQLAlchemy 2.0
- SQLite by default, with a clean PostgreSQL upgrade path
- requests + BeautifulSoup
- pandas + openpyxl

## Local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
cd web
npm install
Copy-Item .env.example .env.local
cd ..
```

## Initialize the database

```powershell
python scripts/init_db.py
```

Optional demo data:

```powershell
python scripts/seed_demo.py
```

## Run the API

```powershell
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --log-level debug
```

Default API URLs:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Run the V2 web app

```powershell
cd web
npm run dev
```

Default web URL:

- [http://127.0.0.1:3000](http://127.0.0.1:3000)

The Next.js backend proxy reads `API_BASE_URL` from `web/.env.local` and defaults to `http://127.0.0.1:8000`.

## Run the legacy Streamlit workspace

```powershell
streamlit run streamlit_app.py
```

Default Streamlit URL:

- [http://127.0.0.1:8501](http://127.0.0.1:8501)

## Run checks

```powershell
python -m pytest -q
cd web
npm run typecheck
```

## Key environment variables

- `DATABASE_URL`
  Default is `sqlite:///./data/app.db`
- `SQLITE_JOURNAL_MODE`
  Default is `TRUNCATE`. This is a practical default for Windows/OneDrive-style paths where SQLite `WAL` or default journaling can cause `disk I/O error`.
- `GOOGLE_API_KEY`
  Required for live Google discovery and geocoding.
- `API_BASE_URL`
  Optional backend override for the Next.js proxy in `web/`.
- `SENDING_ENABLED`
  Keep disabled for review-first mode.

## Notes

- Sending remains disabled by default.
- WhatsApp support is draft-only unless the official WhatsApp Cloud API is configured later.
- Raw discovery, enrichment, and contact evidence stay append-only.
- Canonical lead fields live on `Lead`, while provenance remains in `LeadContact`, `LeadEnrichmentRecord`, and `RawDiscoveryRecord`.
