# Contributing

This repository is still in MVP mode.
Keep changes small, explicit, and easy to verify.

## Before You Start

- Primary runtime path is `backend/`
- Default development mode is `PROVIDER_MODE=mock`
- `frontend/` is a legacy prototype, not the main product path
- Product and architecture decisions live in [`docs/`](./docs)

Start here if you need project context:

- [`README.md`](./README.md)
- [`docs/README.md`](./docs/README.md)
- [`docs/current-functional-flow.md`](./docs/current-functional-flow.md)

## Local Setup

Recommended backend setup:

```bash
cd backend
cp .env.example .env
uv sync
RELOAD=1 uv run python run_server.py
```

Useful URLs:

- `http://127.0.0.1:5060/`
- `http://127.0.0.1:5060/tracked`
- `http://127.0.0.1:5060/api/health`

## Development Rules

- Prefer modifying the FastAPI backend and FastAPI-served web UI first
- Keep provider behavior deterministic in `mock` mode
- Do not make `real` mode a requirement for normal local development
- When changing acceptance or provider flows, keep docs and scripts aligned
- When changing runtime defaults, update both code and operator-facing docs

## Validation

Run the smallest useful validation set for your change.

### Minimum for Backend Changes

```bash
cd backend
uv run python -m unittest discover -s tests -v
```

### Local Acceptance

```bash
backend/.venv/bin/python scripts/local_acceptance.py --skip-ui
TRENDSCOPE_UI_DRIVER=inprocess backend/.venv/bin/python scripts/local_acceptance.py
backend/.venv/bin/python scripts/local_acceptance.py --skip-ui --json
```

### Real Provider Validation

Only run this in a networked environment with real credentials or reachable upstreams:

```bash
cd backend
uv run python -m app.cli provider-status
uv run python -m app.cli provider-verify --probe-mode real
uv run python -m app.cli provider-smoke openai/openai-python --probe-mode real
```

If you need the full acceptance workflow:

```bash
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto --run-ui --ui-python /path/to/python-with-playwright
```

## Documentation Expectations

Update docs when you change:

- provider behavior
- acceptance workflow
- runtime defaults
- search or backfill behavior
- operator commands shown in README or `docs/provider-runtime.md`

Relevant docs:

- [`docs/provider-runtime.md`](./docs/provider-runtime.md)
- [`docs/local-acceptance.md`](./docs/local-acceptance.md)
- [`docs/real-provider-acceptance.md`](./docs/real-provider-acceptance.md)

## Commit Hygiene

- Keep commits focused
- Use descriptive commit messages
- Avoid mixing runtime fixes, docs rewrites, and unrelated cleanup in one commit unless the repo is still being bootstrapped

Good examples:

- `Fix GitHub content fallback when releases are missing`
- `Stabilize NewsNow real probe retries`
- `Refresh README for GitHub landing page`

## Files You Should Not Commit

Do not commit local runtime artifacts or machine-specific files:

- `backend/.env`
- `.venv/`
- `node_modules/`
- `trendscope.db`
- `backend/trendscope.db`
- `__pycache__/`
- `*.pyc`
- `*:Zone.Identifier`

The current `.gitignore` already excludes these, but verify before pushing.

## If You Touch Real Provider Logic

Check these areas together:

- [`backend/app/services/provider_verification.py`](./backend/app/services/provider_verification.py)
- [`backend/app/services/providers.py`](./backend/app/services/providers.py)
- [`backend/app/services/provider_smoke.py`](./backend/app/services/provider_smoke.py)
- [`scripts/ui_smoke_test.py`](./scripts/ui_smoke_test.py)
- [`scripts/update_real_provider_acceptance_record.py`](./scripts/update_real_provider_acceptance_record.py)

Real-provider regressions often appear first in:

- `provider-verify`
- `provider-smoke`
- `/tracked` provider controls
- acceptance record generation
