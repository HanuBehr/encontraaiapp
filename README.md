# Encontra.ai - B2B Lead Discovery & CNPJ Enrichment Platform

A full-stack lead discovery workspace that finds businesses by niche and location, enriches lead data, prevents duplicates, resolves CNPJ candidates, and exports client-ready spreadsheets.

## Overview

Encontra.ai is a lead discovery and enrichment application built for Brazilian B2B prospecting workflows. The product turns niche-and-location searches into structured lead lists that operators can review, enrich, save, validate, and export instead of managing a pile of raw search results and spreadsheets by hand.

The application combines a FastAPI backend, a Next.js frontend, local persistence for MVP/client installs, and multiple provider integrations for company discovery and CNPJ resolution. It is designed to support a practical operator workflow: search, preview, import, enrich, deduplicate, validate uncertain records, and generate export-ready output for commercial teams.

One of the most important parts of the product is its CNPJ resolution workflow. Instead of blindly writing low-confidence company identifiers, the system combines website extraction, public validation, configurable paid provider search, evidence-based scoring, and a human review queue to reduce wrong CNPJ assignments.

Encontra.ai does not use CPF or person-level lookup. The project intentionally focuses on company-level evidence and reviewable workflows that are safer for real client data handling.

## Why I Built This

I built Encontra.ai to solve a very practical sales problem: finding qualified businesses by segment and location, cleaning the results, enriching the data, and preparing it for outreach or export without forcing operators to manage messy spreadsheets manually.

The project started as an internal lead-generation tool, but it grew into a more complete full-stack workspace because the real pain was never just "finding companies." The harder part was everything that came after discovery: preventing duplicates, deciding which leads were worth keeping, recovering missing information, resolving CNPJ candidates carefully, and exporting something a client or sales team could actually use.

This repo represents that full workflow. It is product-oriented, operationally practical, and built around the kind of messy real-world data problems that show up in Brazilian B2B prospecting.

## Key Features

- Business discovery by niche and location
- Lead preview before import
- Duplicate detection and already-saved lead prevention
- Lead enrichment and website recovery
- CNPJ discovery through website extraction and provider-based company search
- Public CNPJ validation with configurable provider support
- Evidence-based CNPJ scoring
- CNPJ review queue for uncertain matches
- Manual approval and bulk approval for safe review candidates
- Client-facing Excel export
- Docker-based client-machine installation
- Debugging tools for CNPJ resolution diagnostics

## CNPJ Resolution Workflow

The CNPJ flow is designed to prefer accuracy over aggressive auto-fill.

1. **Website extraction**  
   The system scans a lead's website for visible CNPJ patterns when a company publishes its registration number publicly.

2. **Public validation**  
   If a known CNPJ is found, it is validated through public providers such as CNPJa Open or the public CNPJ.ws API.

3. **Paid provider search when configured**  
   If no confirmed CNPJ is found from the website flow, the system can search configured paid providers such as CNPJa Commercial. Fallback provider support for CNPJ.ws Premium and CNPJota is also available in the codebase.

4. **Evidence-based scoring**  
   Candidates are scored using company-level signals such as name similarity, municipality/state, address, ZIP code, phone area, domain/email evidence, and related activity data when available.

5. **Review queue for uncertain matches**  
   Ambiguous or medium-confidence matches are intentionally held for review instead of being written automatically.

6. **Manual approval**  
   Operators can inspect candidate details, approve a chosen CNPJ, or leave the lead unresolved.

7. **Export only confirmed CNPJs**  
   The export flow only includes approved or confirmed CNPJ values, reducing the risk of shipping incorrect identifiers to clients or sales teams.

This workflow is intentionally conservative. Pending and review states are part of the product design, not a bug: they exist to reduce bad CNPJ assignments in exported data.

## Tech Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- SQLite
- pytest
- Provider integrations for Google Places, CNPJa, CNPJ.ws, and CNPJota

### Frontend

- Next.js
- React
- TypeScript

### Data & Export

- Local SQLite persistence for MVP/client delivery
- Excel export pipeline for client-ready spreadsheets

### Infrastructure

- Docker
- Docker Compose
- PowerShell helper scripts for Windows client installs

### External APIs

- Google Places / geocoding
- CNPJa Open and CNPJa Commercial
- Optional/configurable CNPJ.ws and CNPJota support

## Architecture

```text
Frontend (Next.js)
        ->
API Proxy
        ->
Backend (FastAPI)
        ->
SQLite / Providers / Export Service
        ->
Google Places / CNPJa / CNPJ providers
```

- The frontend talks to the backend through an API proxy layer.
- The backend owns discovery, enrichment, CNPJ scoring, review metadata, and Excel export generation.
- SQLite is used for MVP and local client-machine delivery.
- Docker Compose runs frontend and backend together for non-developer installations.

## Technical Highlights

- Provider-based CNPJ resolution pipeline with public validation and paid search fallbacks
- Evidence scoring that avoids writing low-confidence CNPJs automatically
- Review queue for ambiguous matches and manual/bulk approval workflow
- Client-install packaging with Docker Compose and Windows helper scripts
- Local debugging script for inspecting CNPJ resolution attempts and score breakdowns
- Excel export flow designed for handoff to client-facing sales operations

## Data Quality & Safety

- Duplicate prevention keeps the same business from being imported repeatedly.
- Already-saved lead detection helps operators avoid cluttering the workspace.
- CNPJ scoring and review steps reduce the chance of exporting incorrect company identifiers.
- Exports only include confirmed or approved CNPJ values.
- The project intentionally avoids CPF and person-level lookup.
- Secrets belong in `.env` files and must never be committed.

## Getting Started

### Option A - Docker client install

This is the recommended path for non-developer usage and client-machine installation.

```powershell
mkdir C:\EncontraAI -Force
cd C:\EncontraAI

git clone https://github.com/HanuBehr/encontraaiapp.git
cd C:\EncontraAI\encontraaiapp

.\scripts\client_install.ps1
notepad .env
.\scripts\client_start.ps1
```

Then open:

- [http://localhost:3000](http://localhost:3000)

Useful follow-up commands:

```powershell
.\scripts\client_logs.ps1
.\scripts\client_backup.ps1
.\scripts\client_stop.ps1
```

For the full end-user installation guide, see [README_CLIENT_INSTALL.md](README_CLIENT_INSTALL.md).

### Option B - local development

Backend:

```powershell
cd "C:\Users\hanub\OneDrive\Documentos\Work\Encontra.ai\encontraaiapp"
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
cd "C:\Users\hanub\OneDrive\Documentos\Work\Encontra.ai\encontraaiapp\web"
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open:

- [http://localhost:3000](http://localhost:3000)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Environment Variables

Core runtime values live in `.env`.

Important examples:

- `GOOGLE_API_KEY`  
  Required for Google Places discovery and geocoding.

- `DATABASE_URL`  
  Local default: `sqlite:///./data/app.db`

- `CNPJ_LOOKUP_PROVIDER`  
  Selects the public known-CNPJ validation provider.

- `CNPJ_COMPANY_SEARCH_ENABLED`  
  Enables paid company-search flows when configured.

- `CNPJ_COMPANY_SEARCH_PROVIDER`  
  Selects the paid company-search provider, such as `cnpja_commercial`.

- `CNPJA_API_KEY`  
  Required for CNPJa Commercial search.

- `BACKEND_URL`  
  Used by the frontend proxy in Docker/client-machine deployments.

Templates:

- [`.env.example`](.env.example)
- [`.env.client.example`](.env.client.example)
- [`web/.env.example`](web/.env.example)

## Repository Structure

```text
app/        FastAPI backend, services, provider integrations, exports
web/        Next.js frontend and API proxy
scripts/    Local ops, client install helpers, debug tooling
data/       Local SQLite database and local runtime data
exports/    Generated export files
backups/    Client-side backup destination
```

## Operations & Debugging

- `scripts/debug_cnpja_resolution.py` helps inspect how a lead is resolved, which attempts were planned or executed, what candidates were returned, and why the final decision became `matched`, `needs_review`, or `not_found`.
- The client install flow includes scripts for setup, start, stop, logs, backup, update, and packaging.
- Docker-based delivery is aimed at practical client installations without requiring manual Python or Node setup.

## Current Scope

Encontra.ai is intentionally focused on the lead discovery and enrichment workflow. It is presented here as a serious full-stack product project, but it does **not** currently implement:

- authentication
- billing
- CRM features
- campaign automation
- multi-tenant account management

That scope is deliberate. The value in this project is the operational workflow: turning raw business discovery into structured, exportable, reviewable lead data.

## Checks

```powershell
python -m pytest -q
cd web
npm run typecheck
```
