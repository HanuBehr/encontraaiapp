# Contributing

This project is maintained as a professional full-stack product repository. Keep changes small, reviewable, and easy to verify.

## Commit Style

Use conventional-style commit prefixes for new work:

- `feat:` for product features
- `fix:` for bug fixes
- `docs:` for documentation-only changes
- `chore:` for tooling, ignore rules, or maintenance
- `refactor:` for behavior-preserving code restructuring
- `test:` for test additions or test-only changes

Examples:

```text
feat: add guided demo scenarios
fix: handle missing backend URL in demo mode
docs: polish repository presentation
chore: update ignored runtime artifacts
refactor: simplify lead export scope handling
test: cover CNPJ review queue edge cases
```

## Verification

Run checks that match the area changed.

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

Hosted demo mode:

```powershell
cd web
cmd.exe /c "set NEXT_PUBLIC_DEMO_MODE=true&& npm run build"
```

## Repository Hygiene

Do not commit:

- `.env` or local environment files
- API keys or provider credentials
- local databases
- generated exports
- build outputs
- dependency folders
- caches

Expected local-only paths include:

- `.venv/`
- `data/`
- `exports/`
- `backups/`
- `dist/`
- `web/.next/`
- `web/node_modules/`
- `web/tsconfig.tsbuildinfo`

Keep provider secrets backend-only. Do not create `NEXT_PUBLIC_*` variables for private API keys.
