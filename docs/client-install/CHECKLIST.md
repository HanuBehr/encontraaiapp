# Client Install Checklist

## Before going to the client

- Repo pushed and ready
- Docker Desktop installer ready
- Git installer ready
- Google API key available
- CNPJA API key available only if CNPJ enrichment will be used
- Client machine has internet access
- Client machine allows admin actions if Docker Desktop requires them

## On the client machine

1. Install Docker Desktop
2. Install Git
3. Clone the repo into `C:\EncontraAI\encontraaiapp`
4. Run `.\scripts\client_install.ps1`
5. Fill `.env`
6. Run `.\scripts\client_start.ps1`
7. Open [http://localhost:3000](http://localhost:3000)
8. Test [http://localhost:8000/health](http://localhost:8000/health)
9. Run one small lead search
10. If CNPJA is configured, run one CNPJ enrichment
11. Run one Excel export
12. Run `.\scripts\client_backup.ps1`

## Emergency fallback

- Collect logs with `.\scripts\client_logs.ps1`
- Stop the app with `.\scripts\client_stop.ps1`
- Back up data with `.\scripts\client_backup.ps1`
