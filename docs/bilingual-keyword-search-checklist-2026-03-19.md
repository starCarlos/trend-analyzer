# Bilingual Keyword Search Checklist (2026-03-19)

## Goal

When the user searches with a Chinese plain keyword, fetch real archive history with both the original Chinese query and a best-effort English variant so the trend line and content list are less language-biased.

## Checklist

- [x] Confirm the current keyword pipeline only uses the original query text
- [x] Add a small keyword-variant helper for Chinese plain keywords
- [x] Wire keyword archive/history search to use bilingual variants without affecting GitHub repo queries
- [x] Add focused tests covering translated-variant fetch and visible result filtering
- [x] Run focused verification
- [ ] Commit this batch

## Notes

- Keep this batch scoped to Chinese plain keywords only
- Failing to translate must degrade back to the original query instead of breaking search
- The returned trend line and content must still come from real providers only
