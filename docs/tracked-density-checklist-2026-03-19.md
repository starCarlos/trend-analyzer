# Tracked Density Checklist (2026-03-19)

## Goal

Make `/tracked` feel lighter after the operations refactor by removing repeated actions and reducing card noise.

## Checklist

- [x] Identify repeated controls and low-value text on tracked cards
- [x] Remove duplicated "open trend" action from tracked cards
- [x] Shrink the visual weight of the untrack control
- [x] Compress tracked page helper copy
- [x] Run focused frontend verification
- [x] Commit this batch

## Notes

- The tracked title itself already acts as the primary jump-back control
- Secondary information should support scanability, not compete with the query name
- Focused verification used:
  - `node --check backend/app/web/app.js`
  - `git diff --check -- backend/app/web/app.js backend/app/web/styles.css docs/tracked-density-checklist-2026-03-19.md`
  - `curl --noproxy '*' -fsS http://127.0.0.1:5081/assets/app.js?v=20260319-ui-refresh-12`
