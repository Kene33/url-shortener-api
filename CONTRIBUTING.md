# Contributing

Use this guide if you want to work on LinkCutter without changing the repository shape by accident.

## Development Setup

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn main:app --app-dir src --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Compose stack:

```bash
cp .env.example .env
docker compose up --build
```

## What To Check Before You Open A PR

Run the same commands the repository CI uses:

```bash
ruff check .
pytest --cov=src --cov-report=term-missing --cov-report=xml
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
```

Optional local coverage:

```bash
cd frontend
npm run test:e2e
```

## Project Notes

- The backend stores state in SQLite and treats Redis as an optional cache.
- Compose publishes the app on `127.0.0.1:3000` and the FastAPI docs on `127.0.0.1:8000/docs`.
- Direct backend runs use `PUBLIC_BASE_URL=http://localhost:8000` unless you override it.
- Admin role bootstrap comes from `ADMIN_EMAILS`. Set it before the target account registers.
- Development auth flows can expose debug verification tokens and 2FA codes. Do not copy those responses into issues or commits.

## Contribution Scope

Keep changes small and reviewable:

- explain the user-facing effect in the PR description
- mention any env changes or data migrations
- update docs when API shape, routes, or setup steps change
- add or adjust tests when behavior changes

## Reporting Bugs

Include:

- the path or screen you used
- the request payload or UI action
- the expected result
- the actual result
- logs, tracebacks, or response bodies when they help

Route security issues through [SECURITY.md](./SECURITY.md).
