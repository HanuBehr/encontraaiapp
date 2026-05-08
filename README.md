# Encontra.ai

## B2B Lead Discovery & CNPJ Enrichment Platform

Encontra.ai is a full-stack lead discovery and enrichment platform built for Brazilian B2B prospecting. It helps users find companies by niche and location, clean and deduplicate lead data, resolve CNPJ candidates through provider integrations, review uncertain matches, and export client-ready spreadsheets.

Built as a practical SaaS-style product for real lead operations, not as a demo toy.

## Overview

Encontra.ai turns raw business searches into a structured operating workflow. Instead of stopping at search results, the product supports preview, import, deduplication, enrichment, CNPJ resolution, review, and export inside one workspace.

The project was designed around a common operational problem: commercial teams spend too much time finding and cleaning prospects before they can actually start selling. In Brazilian B2B data, company names, trade names, legal names, websites, addresses, and CNPJs often do not line up neatly. Encontra.ai is built to handle that mess in a controlled way.

## Why I Built It

I built Encontra.ai to solve a real sales-operations problem: turning niche-and-location searches into clean lead lists that sales teams can actually use. The hard part was not only finding businesses, but handling duplicates, incomplete data, uncertain CNPJ matches, and export formats without forcing operators to clean everything manually in spreadsheets.

What started as an internal lead-generation tool evolved into a more complete SaaS-style MVP because the real value was in the workflow around the data, not just the initial search. The product had to be useful when the data was incomplete, ambiguous, or inconsistent, which is exactly where most prospecting tools become operationally painful.

## Key Features

- Lead discovery by niche and city or region
- Lead preview before import
- Duplicate and already-saved lead prevention
- Lead enrichment workflow
- CNPJ discovery and validation
- Evidence-based CNPJ candidate scoring
- Human-in-the-loop CNPJ review queue
- Manual and bulk candidate approval
- Client-ready Excel export
- Docker-based local installation
- Debug tools for CNPJ resolution diagnostics

## CNPJ Resolution Workflow

This is one of the strongest parts of the product.

1. **Website extraction**  
   The system first tries to find a CNPJ published on the company's own website.

2. **Public validation**  
   Known CNPJ values are validated through public lookup providers such as CNPJA Open and the public CNPJ.ws API.

3. **Commercial provider search**  
   When configured, the platform can use CNPJA Commercial to search candidates using evidence such as name, alias, municipality, ZIP code, domain, and category signals.

4. **Evidence scoring**  
   Candidates are compared against business name, trade name, legal name, city/state, CEP, address, phone, domain/email, and category/CNAE signals.

5. **Review queue**  
   Uncertain or ambiguous candidates are sent to a review queue instead of being blindly written to the lead.

6. **Approval and export**  
   Only confirmed or manually approved CNPJs are exported.

The system is designed to reduce wrong CNPJ assignments, not pretend that every lead can be matched automatically.

## Tech Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- SQLite for MVP and local deployment
- pytest

### Frontend

- Next.js
- React
- TypeScript

### Integrations

- Google Places
- CNPJA
- Optional fallback CNPJ provider adapters where configured

### Data and Export

- Excel export workflow
- CNPJ scoring and review metadata

### Deployment

- Docker
- Docker Compose
- PowerShell install, start, and backup scripts for Windows client machines

## Architecture

```text
Next.js Frontend
        ->
API Proxy
        ->
FastAPI Backend
        ->
SQLite + Enrichment Services + Export Service
        ->
Google Places / CNPJA / CNPJ Provider Integrations
```

- The frontend talks to the backend through an API proxy layer.
- The backend owns discovery, enrichment, CNPJ scoring, review metadata, and export generation.
- SQLite is used for MVP and local client delivery.
- Docker Compose is used for local and client-machine installation.

## Data Quality and Safety

- Duplicate prevention is part of the normal workflow, not an afterthought.
- Existing leads are detected before import.
- CNPJ assignments are scored before confirmation.
- Ambiguous candidates stay reviewable instead of being auto-filled recklessly.
- Exported spreadsheets only include confirmed or manually approved CNPJs.
- The project intentionally does not perform CPF or person-level lookup.
- Secrets belong in `.env` files and are never meant to be committed.

## Getting Started

### Option A - Docker client install

Recommended for non-developer usage and client-machine installation.

```powershell
git clone https://github.com/HanuBehr/encontraaiapp.git
cd encontraaiapp

.\scripts\client_install.ps1
notepad .env
.\scripts\client_start.ps1
```

Then open [http://localhost:3000](http://localhost:3000).

Full practical install guide: [README_CLIENT_INSTALL.md](README_CLIENT_INSTALL.md)

### Option B - Local development

Backend:

```powershell
git clone https://github.com/HanuBehr/encontraaiapp.git
cd encontraaiapp

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\init_local_db.py
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --log-level debug
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

## Environment

Core templates:

- [`.env.example`](.env.example)
- [`.env.client.example`](.env.client.example)
- [`web/.env.example`](web/.env.example)

Important runtime values include:

- `GOOGLE_API_KEY`
- `DATABASE_URL`
- `CNPJ_LOOKUP_PROVIDER`
- `CNPJ_COMPANY_SEARCH_ENABLED`
- `CNPJ_COMPANY_SEARCH_PROVIDER`
- `CNPJA_API_KEY`
- `BACKEND_URL`

## Repository Structure

```text
app/        FastAPI backend, services, provider integrations, exports
web/        Next.js frontend and API proxy
scripts/    Local ops, client install helpers, and debug tooling
data/       Local SQLite runtime data
exports/    Generated export files
backups/    Client-side backups
```

## Operational Notes

- `scripts/debug_cnpja_resolution.py` helps inspect how a lead was matched, reviewed, or rejected during CNPJ resolution.
- The client package includes install, start, stop, log, backup, and update scripts for Windows environments.
- Docker support exists to make client-machine installation practical without manual Python or Node setup.

## Current Scope

Encontra.ai is intentionally focused on lead discovery, enrichment, CNPJ resolution, review, and export. It does not currently implement:

- authentication
- billing
- CRM features
- campaign automation
- multi-tenant account management

That scope is deliberate. The value of the project is the workflow that turns raw business discovery into structured, reviewable, exportable lead data.
