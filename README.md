# TrendScope

TrendScope is a local-first MVP scaffold for cross-platform trend analysis.
It currently focuses on two upstream sources:

- GitHub repository history and content
- NewsNow snapshot data for repository queries and plain keywords

The project is built around a FastAPI backend that serves both the API and the default web UI directly.

## Current Status

- Runtime path: `backend/` FastAPI app is the primary product path
- Default provider mode: `mock`
- Real-provider validation: supported through CLI, `/tracked`, and acceptance scripts
- Frontend note: `frontend/` is kept as a legacy Next.js prototype, not the current runtime

## What Works Today

- Search GitHub repositories and plain keywords
- Return partial results immediately and backfill missing data asynchronously
- Show trend series, daily snapshot data, and content items
- Track and untrack keywords from the UI
- Run provider preflight, `Verify real`, and `Run smoke` from `/tracked`
- Execute local acceptance and real-provider acceptance from scripts

## Quick Start

### Recommended Run

```bash
cd backend
cp .env.example .env
uv sync
RELOAD=1 uv run python run_server.py
```

Open these URLs after startup:

- Search page: `http://127.0.0.1:5081/`
- Tracked page: `http://127.0.0.1:5081/tracked`
- Health check: `http://127.0.0.1:5081/api/health`

### Alternative Start

```bash
cd backend
uv run uvicorn app.main:app --reload
```

## Provider Modes

- `PROVIDER_MODE=mock`
  - Fully offline
  - Deterministic data for local development and tests
- `PROVIDER_MODE=real`
  - Use GitHub and NewsNow directly
  - Exposes real upstream failures instead of falling back
- `PROVIDER_MODE=auto`
  - Prefer real providers
  - Fall back to mock when a real request fails

Ready-made env templates:

- [`backend/.env.example`](./backend/.env.example)
- [`backend/.env.auto.example`](./backend/.env.auto.example)
- [`backend/.env.real.example`](./backend/.env.real.example)

Runtime guide:

- [`docs/provider-runtime.md`](./docs/provider-runtime.md)

## Useful Commands

### Tests

```bash
cd backend
uv run python -m unittest discover -s tests -v
```

### CLI

```bash
cd backend
uv run python -m app.cli health
uv run python -m app.cli search openai/openai-python
uv run python -m app.cli track openai/openai-python
uv run python -m app.cli scheduler-status
uv run python -m app.cli provider-status
uv run python -m app.cli provider-verify --probe-mode real
uv run python -m app.cli provider-smoke openai/openai-python --probe-mode real
uv run python -m app.cli collect-tracked
```

## Acceptance Workflows

### Local Acceptance

```bash
backend/.venv/bin/python scripts/local_acceptance.py --skip-ui
TRENDSCOPE_UI_DRIVER=inprocess backend/.venv/bin/python scripts/local_acceptance.py
backend/.venv/bin/python scripts/local_acceptance.py --ui-python /path/to/python-with-playwright
backend/.venv/bin/python scripts/local_acceptance.py --skip-ui --json
```

This script can:

- run backend unit tests
- check or auto-start the FastAPI server
- execute UI smoke checks
- emit machine-readable JSON output

### Real Provider Acceptance

One-command workflow:

```bash
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto --run-ui --ui-python /path/to/python-with-playwright
```

Manual two-step workflow:

```bash
backend/.venv/bin/python scripts/init_real_provider_acceptance_record.py --mode auto
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py --mode auto
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py --mode auto --run-ui --ui-python /path/to/python-with-playwright
```

Related docs:

- [`docs/local-acceptance.md`](./docs/local-acceptance.md)
- [`docs/real-provider-acceptance.md`](./docs/real-provider-acceptance.md)
- [`docs/real-provider-acceptance-record-template.md`](./docs/real-provider-acceptance-record-template.md)
- [`docs/acceptance-records/`](./docs/acceptance-records)

## Repository Layout

```text
backend/   FastAPI app, SQLite models, provider workflows, static web UI
frontend/  legacy Next.js prototype kept for reference
docs/      product, technical, runtime, and acceptance documentation
scripts/   local acceptance, real-provider acceptance, and smoke helpers
```

## Key Docs

- [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- [`docs/README.md`](./docs/README.md)
- [`docs/product-prd.md`](./docs/product-prd.md)
- [`docs/technical-spec.md`](./docs/technical-spec.md)
- [`docs/mvp-plan.md`](./docs/mvp-plan.md)
- [`docs/current-functional-flow.md`](./docs/current-functional-flow.md)

## API Surface

- `GET /api/health`
- `GET /api/search?q=openai/openai-python&period=30d`
- `GET /api/keywords/{id}/backfill-status`
- `GET /api/provider-status`
- `POST /api/provider-verify`
- `POST /api/provider-smoke`
- `POST /api/keywords/{id}/track`
- `DELETE /api/keywords/{id}/track`

## Notes

- Current priority is still the Python backend path first.
- If you only need the working product path, start from `backend/`, not `frontend/`.
