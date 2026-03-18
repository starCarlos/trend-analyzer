# 2026-03-18 Provider Verification Archives Checklist

- [x] Extend provider status payload to cover Google News and GDELT
- [x] Extend provider verify payload to probe Google News and GDELT
- [x] Update provider smoke gating and summaries for all online providers
- [x] Render all provider cards in the tracked operations panel
- [x] Add focused tests for provider status, verify, smoke, and UI rendering

## Notes

- `GET /api/provider-status` now returns `github`, `newsnow`, `google_news`, and `gdelt`.
- `POST /api/provider-verify` now probes all four sources; on this machine the live `real` probe succeeded for all four on `2026-03-18`.
- Provider smoke keeps its default skip gate on the core realtime sources (`github`, `newsnow`), but summaries and next steps now also surface `Google News` and `GDELT` probe failures.
