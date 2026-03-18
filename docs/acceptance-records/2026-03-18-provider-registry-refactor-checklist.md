# 2026-03-18 Provider Registry Refactor Checklist

- [x] Introduce a shared online provider registry with source order and smoke-blocking flags
- [x] Refactor provider status payload to use `providers[]` instead of fixed source fields
- [x] Refactor provider verify payload to use `providers[]` instead of fixed source fields
- [x] Keep legacy `.github/.newsnow/.google_news/.gdelt` accessors for compatibility inside Python code and tests
- [x] Update provider smoke logic to iterate provider registry metadata
- [x] Update tracked-page provider cards to render from `providers[]`
- [x] Add focused regression tests for registry-backed provider status / verify / smoke / UI wiring

## Notes

- New shared registry lives in `backend/app/services/provider_registry.py`.
- Live `GET /api/provider-status` on `2026-03-18` confirmed the API now returns provider cards as an ordered `providers[]` array.
- Live `POST /api/provider-verify` on `2026-03-18` confirmed the new `providers[]` verify payload shape; `GDELT` may still fail transiently with HTTP 429 because of the upstream 5-second rate limit.
