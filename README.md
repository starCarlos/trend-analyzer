# TrendScope

TrendScope is a local-first MVP scaffold for cross-platform trend analysis.
The repository currently contains:

- product and implementation docs in [`docs/`](./docs)
- a FastAPI backend with deterministic mock collectors
- a FastAPI-served search page that runs without Node.js

The code intentionally focuses on the MVP path documented in:

- [`docs/product-prd.md`](./docs/product-prd.md)
- [`docs/technical-spec.md`](./docs/technical-spec.md)
- [`docs/mvp-plan.md`](./docs/mvp-plan.md)

## Repository Layout

```text
backend/   FastAPI app, SQLite models, backfill workflow, static web UI
frontend/  legacy Next.js UI prototype kept in repo, not required for runtime
docs/      Product, technical, and planning documents
```

## Backend

### Recommended Direct Run

```bash
cd backend
cp .env.example .env
uv sync
RELOAD=1 uv run python run_server.py
```

这是当前推荐的运行方式：

- 只启动 Python 后端
- 后端会同时提供 API 和网页
- 适合直接联调 API、CLI、scheduler 和 SQLite

启动后访问：

- 网页：`http://127.0.0.1:8000/`
- 追踪页：`http://127.0.0.1:8000/tracked`
- 健康检查：`http://127.0.0.1:8000/api/health`

### Alternative Start

```bash
cd backend
uv run uvicorn app.main:app --reload
```

### Environment

Copy [`backend/.env.example`](./backend/.env.example) to `backend/.env` and adjust values if needed.

If you want ready-made templates for real providers, use:

- [`backend/.env.auto.example`](./backend/.env.auto.example)
- [`backend/.env.real.example`](./backend/.env.real.example)
- runtime guide: [`docs/provider-runtime.md`](./docs/provider-runtime.md)

The backend now supports provider switching:

- `PROVIDER_MODE=mock`
  default, fully offline, deterministic data
- `PROVIDER_MODE=real`
  use GitHub and NewsNow directly
- `PROVIDER_MODE=auto`
  try real providers first, fall back to mock if requests fail

The mock provider remains the default so local development and tests do not require external access.

### Automatic Collection

The backend now includes a built-in background scheduler for tracked keywords.
It is disabled by default and controlled with:

- `SCHEDULER_ENABLED`
- `SCHEDULER_INTERVAL_SECONDS`
- `SCHEDULER_INITIAL_DELAY_SECONDS`
- `SCHEDULER_PERIOD`
- `SCHEDULER_RUN_BACKFILL_NOW`

### `uv` Notes

- The backend dependency graph is locked with `uv.lock`
- `uv sync` creates and manages `.venv` automatically
- Use `uv run <command>` for all backend commands

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

## Web UI

当前默认 UI 已由 FastAPI 直接提供，不需要 Node.js。

仓库里的 `frontend/` 目录保留为旧版原型参考，但不是当前运行路径。

当前可直接访问：

- 搜索页：`/`
- 追踪页：`/tracked`
  - 包含追踪列表、scheduler 状态、provider 预检、`Verify real` 在线探测、`Run smoke` 联调总览、手动采集和最近采集日志

`/tracked` 页的 `Provider preflight` 面板现在可直接完成：

- 查看本地 provider 预检结果
- 点击 `Verify real` 做轻量在线探测
- 输入 smoke query / period，按需勾选 `Force real search`
- 点击 `Run smoke` 查看 summary、search 状态、availability 和 next steps

### Smoke Test Script

The repository includes [`scripts/ui_smoke_test.py`](./scripts/ui_smoke_test.py) for browser-based local smoke testing.
It expects:

- backend running on `127.0.0.1:8000`
- Playwright Chromium installed

The script now covers both:

- search page load + Track/Untrack readiness
- `/tracked` page `Run smoke` provider flow

### Local Acceptance

The repository also includes [`scripts/local_acceptance.py`](./scripts/local_acceptance.py) as a one-command local acceptance entry.

Typical usage:

```bash
backend/.venv/bin/python scripts/local_acceptance.py --skip-ui
backend/.venv/bin/python scripts/local_acceptance.py --ui-python /path/to/python-with-playwright
backend/.venv/bin/python scripts/local_acceptance.py --skip-ui --json
```

What it does:

- run backend unit tests unless `--skip-tests`
- check whether `http://127.0.0.1:8000/api/health` is already up
- auto-start `backend/run_server.py` if needed unless `--require-running`
- run `scripts/ui_smoke_test.py` unless `--skip-ui`
- emit a machine-readable JSON summary when `--json` is enabled

For a networked real-provider validation run, use:

- [`docs/real-provider-acceptance.md`](./docs/real-provider-acceptance.md)
- [`docs/real-provider-acceptance-record-template.md`](./docs/real-provider-acceptance-record-template.md)

One-command workflow:

```bash
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto --run-ui --ui-python /path/to/python-with-playwright
```

What it does:

- initialize or reuse the dated acceptance record
- run `scripts/local_acceptance.py` first by default
- update CLI sections automatically
- when `--run-ui` is enabled, auto-start the FastAPI server if needed and write page validation results back to the record
- auto-fill PRD mapping and final conclusion sections

If you want the manual two-step flow instead:

```bash
backend/.venv/bin/python scripts/init_real_provider_acceptance_record.py --mode auto
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py --mode auto
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py --mode auto --run-ui --ui-python /path/to/python-with-playwright
```

## MVP Endpoints

- `GET /api/health`
- `GET /api/search?q=openai/openai-python&period=30d`
- `GET /api/keywords/{id}/backfill-status`
- `GET /api/provider-status`
- `POST /api/provider-verify`
- `POST /api/provider-smoke`
- `POST /api/keywords/{id}/track`
- `DELETE /api/keywords/{id}/track`

## Notes

- 当前推荐优先级是：先直接运行 Python 后端。
