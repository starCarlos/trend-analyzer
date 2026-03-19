# 2026-03-19 Provider Card Merge Checklist

- [completed] Merge provider verify results into the existing provider cards instead of appending duplicate cards.
- [completed] Bump the frontend asset version to avoid stale browser cache.
- [completed] Run a focused verification on the merged provider grid rendering logic.

Verification:
- Confirmed `/` now serves `app.js?v=20260319-ui-refresh-10`.
- Confirmed served `app.js` renders provider cards with an optional merged `probe` block.
- Confirmed served `app.js` now builds `probesBySource` and renders one card per provider source.
