# TrendScope

TrendScope is a local-first trend analysis app built around a FastAPI backend that serves both the API and the default web UI directly.

The current product path is `backend/`. The `frontend/` directory is a legacy Next.js prototype kept only for reference.

## Current Status

- Primary runtime: `FastAPI + SQLite + built-in static web UI`
- Default local URL: `http://127.0.0.1:5081`
- Default provider mode: `mock`
- Core real providers: `GitHub` and `NewsNow`
- Optional archive/history providers: `Google News`, `Direct RSS`, and `GDELT`
- Real-provider validation is available from `CLI`, `/tracked`, and acceptance scripts

## What Works Today

- Search GitHub URLs, `owner/repo`, plain keywords, and bare repo names that resolve cleanly
- Expand plain-keyword searches across Chinese and English variants, then merge and dedupe results
- Return partial results immediately and backfill missing history/content asynchronously
- Show trend lines, daily snapshot cards, availability states, and content items
- Track and untrack queries from the search page
- Manage tracked items on `/tracked`
- Run provider preflight, `Verify real`, `Run smoke`, scheduler checks, and manual collection from `/tracked`
- Execute local acceptance and real-provider acceptance, including isolated scheduler and failure-readability probes

## Quick Start

### Recommended Local Run

```bash
cd backend
cp .env.example .env
uv sync
PORT=5081 RELOAD=1 uv run python run_server.py
```

Open these URLs after startup:

- Search page: `http://127.0.0.1:5081/`
- Tracked page: `http://127.0.0.1:5081/tracked`
- Health check: `http://127.0.0.1:5081/api/health`

### Docker Run

```bash
docker compose up --build
```

The compose file also exposes the app on `http://127.0.0.1:5081`.

### Alternative Start

```bash
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 5081 --reload
```

## Provider Modes

- `PROVIDER_MODE=mock`
  - Fully offline
  - Deterministic data for local development and tests
- `PROVIDER_MODE=real`
  - Use real upstreams directly
  - Expose upstream failures instead of falling back
- `PROVIDER_MODE=auto`
  - Prefer real upstreams
  - Fall back to mock when a real request fails

Ready-made env templates:

- [`backend/.env.example`](./backend/.env.example)
- [`backend/.env.auto.example`](./backend/.env.auto.example)
- [`backend/.env.real.example`](./backend/.env.real.example)

Provider runtime guide:

- [`docs/provider-runtime.md`](./docs/provider-runtime.md)

## Real-Provider Coverage

### Core Providers

- `GitHub`
  - repository history
  - repository content
- `NewsNow`
  - daily snapshot
  - content stream

### Optional Archive and History Providers

- `Google News`
- `Direct RSS`
- `GDELT`

These optional providers enrich keyword history and content completeness, but the default real-search blocking path still centers on `GitHub` and `NewsNow`.

### Useful Runtime Knobs

- `NEWSNOW_SOURCE_IDS`
- `GOOGLE_NEWS_ENABLED`
- `DIRECT_RSS_ENABLED`
- `GDELT_ENABLED`
- `ARCHIVE_AMBIGUOUS_QUERY_CONTEXTS_JSON`
- `REQUEST_TIMEOUT_SECONDS`
- `HTTP_PROXY`

`ARCHIVE_AMBIGUOUS_QUERY_CONTEXTS_JSON` lets you constrain ambiguous keywords with extra context. Example:

```json
{
  "manus": ["ai", "agent", "agents"],
  "claude": ["anthropic", "code", "ai"]
}
```

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
uv run python -m app.cli search openai/openai-python --period 30d
uv run python -m app.cli track openai/openai-python
uv run python -m app.cli list-tracked
uv run python -m app.cli scheduler-status
uv run python -m app.cli provider-status
uv run python -m app.cli provider-verify --probe-mode real
uv run python -m app.cli provider-smoke openai/openai-python --period 30d --probe-mode real
uv run python -m app.cli collect-tracked --period 30d
```

### API Examples

```bash
curl 'http://127.0.0.1:5081/api/health'
curl 'http://127.0.0.1:5081/api/search?q=openai/openai-python&period=30d'
curl 'http://127.0.0.1:5081/api/search?q=oil&period=30d&content_source=google_news'
curl 'http://127.0.0.1:5081/api/keywords?tracked_only=true'
curl 'http://127.0.0.1:5081/api/collect/status'
curl 'http://127.0.0.1:5081/api/collect/logs?limit=20'
```

`content_source` currently supports:

- `all`
- `github`
- `newsnow`
- `google_news`
- `direct_rss`
- `gdelt`

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

### Real-Provider Acceptance

One-command workflow:

```bash
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto --run-ui --ui-python /path/to/python-with-playwright
```

Manual record workflow:

```bash
backend/.venv/bin/python scripts/init_real_provider_acceptance_record.py --mode auto
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py --mode auto
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py --mode auto --run-ui --ui-python /path/to/python-with-playwright
```

In `real` mode, the record updater now also runs isolated temporary probes to verify:

- empty-database startup
- scheduler-driven tracked collection
- readable failure states for `search`, `backfill`, and `collect`

Related docs:

- [`docs/local-acceptance.md`](./docs/local-acceptance.md)
- [`docs/real-provider-acceptance.md`](./docs/real-provider-acceptance.md)
- [`docs/real-provider-acceptance-record-template.md`](./docs/real-provider-acceptance-record-template.md)
- [`docs/acceptance-records/`](./docs/acceptance-records)

## Repository Layout

```text
backend/   FastAPI app, SQLite models, provider workflows, CLI, and static web UI
frontend/  legacy Next.js prototype kept for reference
docs/      product, technical, runtime, and acceptance documentation
scripts/   local acceptance, real-provider acceptance, and smoke helpers
```

## Key Docs

- [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- [`docs/README.md`](./docs/README.md)
- [`docs/product-prd.md`](./docs/product-prd.md)
- [`docs/technical-spec.md`](./docs/technical-spec.md)
- [`docs/current-functional-flow.md`](./docs/current-functional-flow.md)
- [`docs/mvp-completion-checklist.md`](./docs/mvp-completion-checklist.md)

## API Surface

- `GET /api/health`
- `GET /api/search?q=<query>&period=<7d|30d|90d|all>&content_source=<...>`
- `GET /api/keywords/{id}/backfill-status`
- `GET /api/keywords`
- `POST /api/keywords`
- `POST /api/keywords/{id}/track`
- `DELETE /api/keywords/{id}/track`
- `POST /api/collect/trigger`
- `GET /api/collect/status`
- `GET /api/collect/logs`
- `GET /api/provider-status`
- `POST /api/provider-verify`
- `POST /api/provider-smoke`

## License

The repository code is licensed under [`Apache-2.0`](./LICENSE).

That license covers this repository's code and bundled documentation. It does not
change the terms of third-party data sources or trademarks such as GitHub,
NewsNow, Google News, Direct RSS feeds, or GDELT.

## Notes

- Current priority is the Python backend path first.
- If you only need the working product path, start from `backend/`, not `frontend/`.
