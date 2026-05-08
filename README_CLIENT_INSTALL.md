# Encontra.ai Client Install

## What this installs
- Encontra.ai local app
- Runs on the client computer with Docker
- Browser access at [http://localhost:3000](http://localhost:3000)
- Data saved locally in `./data/app.db`
- Exports saved locally in `./exports`

## Requirements
- Windows 10 or Windows 11
- Docker Desktop installed and running
- Git optional, or the provided zip package
- Google API key
- CNPJá API key

## Recommended install path
`C:\EncontraAI\encontraaiapp`

Important:
Do not install inside OneDrive. Use `C:\EncontraAI\encontraaiapp`.

## Install steps
1. Install Docker Desktop and make sure it is running.
2. Copy or clone this project to `C:\EncontraAI\encontraaiapp`.
3. Open PowerShell in the project folder.
4. Run:

```powershell
.\scripts\client_install.ps1
```

5. Open `.env`.
6. Fill at least:
   - `GOOGLE_API_KEY`
   - `CNPJA_API_KEY`
7. Run:

```powershell
.\scripts\client_start.ps1
```

8. Open:
   - [http://localhost:3000](http://localhost:3000)

## Stop

```powershell
.\scripts\client_stop.ps1
```

## Start again later

```powershell
.\scripts\client_start.ps1
```

## Logs

```powershell
.\scripts\client_logs.ps1
```

## Backup

```powershell
.\scripts\client_backup.ps1
```

## Update

```powershell
.\scripts\client_update.ps1
```

Always back up before updating.

## Build validation note
- Validate `docker compose build` and the first container startup on the client or deployment machine.
- In this Codex/Windows workspace, `npm run build` may hang because of local Next.js/Windows filesystem behavior, so Docker validation should be confirmed outside this environment.

## Troubleshooting
- Docker not running:
  Start Docker Desktop first.
- Port 3000 already in use:
  Stop the other app using port 3000, then run `.\scripts\client_start.ps1` again.
- Port 8000 already in use:
  Stop the other app using port 8000, then run `.\scripts\client_start.ps1` again.
- Missing `.env`:
  Run `.\scripts\client_install.ps1`.
- Invalid API key:
  Recheck `GOOGLE_API_KEY` and `CNPJA_API_KEY` in `.env`.
- CNPJá rate limit:
  Wait about 1 minute and try again.
- Google Places quota:
  Check the quota and billing settings for the Google key.
- Windows Defender or firewall prompt:
  Allow Docker Desktop and local container traffic when prompted.
- OneDrive folder warning:
  Move the project out of OneDrive and use `C:\EncontraAI\encontraaiapp`.

## Data safety
- Never delete `./data` unless intentionally resetting the app.
- Back up before updates.
- `.env` contains secrets and must not be shared publicly.

## Useful local URLs
- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Backend health: [http://localhost:8000/health](http://localhost:8000/health)
