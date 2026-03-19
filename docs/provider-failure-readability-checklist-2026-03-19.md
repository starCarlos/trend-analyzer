# Provider Failure Readability Checklist (2026-03-19)

## Goal

Make provider verification, smoke summaries, and acceptance scripts describe failures consistently, especially when only supplemental archive providers fail.

## Checklist

- [x] Inspect current provider verify / smoke summaries and acceptance script assumptions
- [x] Normalize raw `provider_verify` payload reads to the current `providers[]` shape
- [x] Distinguish core realtime provider failures from supplemental archive provider failures
- [x] Improve smoke next-step wording so non-blocking archive failures do not read as hard blockers
- [x] Add focused tests for the new wording and payload handling
- [x] Run focused verification
- [x] Commit this batch

## Notes

- Core realtime providers: `github`, `newsnow`
- Supplemental archive providers: `google_news`, `direct_rss`, `gdelt`
- Acceptance automation should still treat `github` / `newsnow` as the pass gate for default smoke flow
- Focused verification run:
  - `backend/.venv/bin/python -m py_compile ...`
  - `backend/.venv/bin/python -m unittest backend.tests.test_services -v`
  - `backend/.venv/bin/python -m unittest backend.tests.test_acceptance_scripts -v`
  - `cd backend && .venv/bin/python -m app.cli provider-status`
  - `cd backend && .venv/bin/python -m app.cli provider-verify --probe-mode real`
  - `cd backend && .venv/bin/python -m app.cli provider-smoke openclaw --period 30d --probe-mode real`
