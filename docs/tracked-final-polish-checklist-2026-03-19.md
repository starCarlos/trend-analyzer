# Tracked Final Polish Checklist (2026-03-19)

## Goal

Finish the `/tracked` page cleanup so it clearly reads as a revisit page first, with troubleshooting tools kept secondary.

## Checklist

- [x] Define the final cleanup scope for `/tracked`
- [x] Compress the tracked top area into one lighter summary band
- [x] Reduce top stats to only the most useful signals
- [x] Unify tracked page naming and helper copy
- [x] Keep troubleshooting copy shorter and less dominant
- [x] Run focused verification on local assets and JS syntax
- [x] Commit this batch

## Notes

- The watchlist remains the main interaction on `/tracked`
- Summary UI should support quick scanning, not compete with the list itself
- Focused verification used:
  - `node --check backend/app/web/app.js`
  - `git diff --check -- backend/app/web/index.html backend/app/web/app.js backend/app/web/styles.css docs/tracked-final-polish-checklist-2026-03-19.md`
  - `curl --noproxy '*' -fsS http://127.0.0.1:5081/tracked`
  - `curl --noproxy '*' -fsS http://127.0.0.1:5081/assets/app.js?v=20260319-ui-refresh-13`
