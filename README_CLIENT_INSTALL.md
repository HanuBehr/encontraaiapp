# Encontra.ai Client Installation Guide

This guide explains how to install and run Encontra.ai on a Windows machine using Docker Desktop.

## What This Installs

- A local Encontra.ai environment for the client
- A Dockerized FastAPI backend
- A Dockerized Next.js frontend
- Local persistence for the SQLite database
- Local folders for exports and backups

After installation, the application is available in the browser at [http://localhost:3000](http://localhost:3000).

## What Is Stored Locally

- Application data: `./data/app.db`
- Exported files: `./exports`
- Manual backups: `./backups`

Nothing in this guide requires the client to install Python, Node.js, npm, or a virtual environment manually.

## Requirements

- Windows 10 or Windows 11
- Docker Desktop installed and running
- A Google API key
- A CNPJa API key
- Git is optional if the project is delivered as a zip package

## Recommended Installation Path

`C:\EncontraAI\encontraaiapp`

Important:
Do not install the project inside OneDrive. A normal local folder such as `C:\EncontraAI\encontraaiapp` is strongly recommended.

## Install Steps

1. Install Docker Desktop and make sure it is running.
2. Copy or clone the project to `C:\EncontraAI\encontraaiapp`.
3. Open PowerShell in the project folder.
4. Run:

```powershell
.\scripts\client_install.ps1
```

5. Open the generated `.env` file.
6. Fill at least:
   - `GOOGLE_API_KEY`
   - `CNPJA_API_KEY`
7. Start the application:

```powershell
.\scripts\client_start.ps1
```

8. Open:
   - [http://localhost:3000](http://localhost:3000)

## Daily Commands

Start the application:

```powershell
.\scripts\client_start.ps1
```

Stop the application:

```powershell
.\scripts\client_stop.ps1
```

View logs:

```powershell
.\scripts\client_logs.ps1
```

Create a backup:

```powershell
.\scripts\client_backup.ps1
```

Update from Git:

```powershell
.\scripts\client_update.ps1
```

Always back up before updating.

## Build Validation Note

- Validate `docker compose build` and the first container startup on the client or deployment machine.
- In the local Codex/Windows workspace used during development, `npm run build` may hang because of local Next.js and filesystem behavior. For that reason, final Docker validation should be confirmed outside the Codex workspace.

## Useful URLs

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Backend health check: [http://localhost:8000/health](http://localhost:8000/health)

## Troubleshooting

- **Docker is not running**  
  Start Docker Desktop before using the scripts.

- **Port 3000 is already in use**  
  Stop the other application using port 3000 and run `.\scripts\client_start.ps1` again.

- **Port 8000 is already in use**  
  Stop the other application using port 8000 and run `.\scripts\client_start.ps1` again.

- **Missing `.env`**  
  Run `.\scripts\client_install.ps1` first.

- **Invalid API key**  
  Recheck `GOOGLE_API_KEY` and `CNPJA_API_KEY` in `.env`.

- **CNPJa rate limit**  
  Wait about one minute and retry the operation.

- **Google Places quota**  
  Verify quota and billing settings for the configured Google key.

- **Windows Defender or firewall prompt**  
  Allow Docker Desktop and local container traffic when prompted.

- **Project is inside OneDrive**  
  Move the project to `C:\EncontraAI\encontraaiapp`.

## Data Safety

- Never delete `./data` unless you intentionally want to reset the application.
- Back up before updates.
- `.env` contains secrets and should never be shared publicly.
