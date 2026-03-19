# Keyword Trend Regression Checklist (2026-03-19)

## Goal

Restore real trend lines for plain-keyword searches when one archive provider fails after another provider has already returned valid historical content.

## Checklist

- [x] Reproduce the regression with a real keyword (`石油`) and confirm whether the gap is in data fetch or rendering
- [x] Fix inline keyword history prefetch so one failing archive provider does not roll back already fetched real content
- [x] Add a focused regression test for partial archive-provider failure
- [x] Run focused verification for the affected backend path
- [ ] Commit this batch

## Notes

- Keep the fix minimal and preserve the current "real data only" rule for trend lines
- Prefer protecting already fetched archive/news content over retrying every failing source in the same request
