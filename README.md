# Reverse Logistics Lead Discovery MVP

Production-minded MVP for local B2B lead discovery and outreach for a recycling / reverse-logistics business in Brazil.

## What is implemented

- Google Places discovery ingestion with `ImportBatch` tracking
- append-only raw discovery history
- public-site enrichment with provenance-preserving contact evidence
- lead review API and Streamlit admin UI
- deduplication and canonical merge logic
- lead scoring with stored reasoning
- outreach template seeding and draft generation
- Excel export with `Leads`, `Outreach_Log`, `Templates`, `Settings`, and `Metadata`
- pytest coverage for normalization, enrichment, dedupe, scoring, outreach, export, and API smoke paths

## Stack

- Python 3.11+
- FastAPI
- Streamlit
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
uvicorn app.api.main:app --reload
```

Default API URL:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Run Streamlit

```powershell
streamlit run streamlit_app.py
```

Default Streamlit URL:

- [http://127.0.0.1:8501](http://127.0.0.1:8501)

## Run tests

```powershell
python -m pytest -q
```

## Key environment variables

- `DATABASE_URL`
  Default is `sqlite:///./data/app.db`
- `SQLITE_JOURNAL_MODE`
  Default is `TRUNCATE`. This is a practical default for Windows/OneDrive-style paths where SQLite `WAL` or default journaling can cause `disk I/O error`.
- `GOOGLE_API_KEY`
  Required for live Google discovery and geocoding.
- `SENDING_ENABLED`
  Keep disabled for review-first mode.

## Notes

- Sending remains disabled by default.
- WhatsApp support is draft-only unless the official WhatsApp Cloud API is configured later.
- Raw discovery, enrichment, and contact evidence stay append-only.
- Canonical lead fields live on `Lead`, while provenance remains in `LeadContact`, `LeadEnrichmentRecord`, and `RawDiscoveryRecord`.
