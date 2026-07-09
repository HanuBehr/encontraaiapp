# Documentation

This folder contains the operational documentation for Encontra.ai.

## Deployment Paths

| Goal | Doc | Backend | API keys | Persistence |
| --- | --- | --- | --- | --- |
| Public hosted demo | [`deployment/VERCEL_DEMO.md`](deployment/VERCEL_DEMO.md) | No | No | Browser `sessionStorage` |
| Local development | [`../README.md`](../README.md#getting-started) | FastAPI local process | Google key for real discovery | `./data` |
| Local Windows Docker | [`client-install/README.md`](client-install/README.md) | Docker Compose | Google key for real discovery | `./data` |
| Backend-backed deployment | [`deployment/VERCEL_BACKEND.md`](deployment/VERCEL_BACKEND.md) | Separate backend host | Backend secret manager | Persistent backend disk |

## Product And Demo

- [`DEMO_MODE.md`](DEMO_MODE.md): how the frontend-only demo works, what data it uses, and how browser-local persistence behaves.

## Deployment

- [`deployment/VERCEL_DEMO.md`](deployment/VERCEL_DEMO.md): deploy the hosted frontend demo with no backend or API keys.
- [`deployment/VERCEL_BACKEND.md`](deployment/VERCEL_BACKEND.md): connect a Vercel frontend to a separately hosted backend.
- [`deployment/PRODUCTION_LAUNCH_CHECKLIST.md`](deployment/PRODUCTION_LAUNCH_CHECKLIST.md): first production launch checklist, secret handling, smoke tests, and rollback notes.

## Local Windows Docker

- [`client-install/README.md`](client-install/README.md): install and run the Dockerized app on a Windows machine.
- [`client-install/CHECKLIST.md`](client-install/CHECKLIST.md): short operational checklist for local setup.

## Repository Practices

- [`../CONTRIBUTING.md`](../CONTRIBUTING.md): verification commands, commit message style, and repository hygiene rules.
