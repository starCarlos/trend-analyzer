# Keyword Trend Line Checklist (2026-03-19)

## Goal

Reduce the "no visible trend line" state for plain keyword searches by ensuring the first real lookup can return at least one real snapshot-based trend point when history is not ready yet.

## Checklist

- [x] Confirm why keyword searches can return no visible trend series
- [x] Prefetch a real NewsNow snapshot inline for plain keywords when no fresh snapshot exists
- [x] Keep existing historical-content backfill behavior for true history lines
- [x] Add focused tests for the first-search keyword trend behavior
- [x] Run focused verification
- [ ] Commit this batch

## Notes

- This improves the default case but cannot manufacture a real line when every upstream source returns no data or hard fails
- A one-point real snapshot line is acceptable as a fallback until dated history fills in
