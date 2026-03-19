# Tracked UI Checklist (2026-03-19)

## Goal

Reduce clutter on `/tracked` and make the page read as:

1. Watchlist first
2. Operations second
3. One troubleshooting tool at a time

## Checklist

- [x] Inspect current tracked page structure and pain points
- [x] Add a focused tracked-page UI checklist
- [x] Convert advanced operations area into single-panel switching
- [x] Lower the visual weight of scheduler / provider / collect panels
- [x] Clarify copy for provider preflight and manual collect
- [x] Run focused frontend verification on `/tracked`
- [x] Commit this batch

## Notes

- Search results remain the product center; tracked view should primarily serve revisit and jump-back flows
- Advanced operations should stay available, but no longer compete with the watchlist for attention
- Focused verification used:
  - `curl --noproxy '*' -fsS http://127.0.0.1:5081/tracked`
  - `backend/.venv/bin/python -m py_compile scripts/ui_smoke_test.py scripts/update_real_provider_acceptance_record.py backend/tests/test_acceptance_scripts.py`
  - `backend/.venv/bin/python -m unittest backend.tests.test_acceptance_scripts -v`
  - `backend/.venv/bin/python scripts/ui_smoke_test.py --driver inprocess ...` updated output verified in `/tmp/trendscope-ui-smoke-20260319-tracked.json`
- Real browser click-through could not be re-run in this environment because `playwright` is not installed in `backend/.venv`
