# Bilingual Keyword Search Checklist (2026-03-19)

## Goal

When the user searches with a plain keyword in either Chinese or English, fetch real archive history and snapshots with both the original query and a best-effort counterpart so the trend line and content list are less language-biased.

## Checklist

- [x] Confirm the current keyword pipeline only uses the original query text
- [x] Add a small keyword-variant helper for Chinese plain keywords
- [x] Extend the helper so English plain keywords can also add a Chinese variant
- [x] Wire keyword archive/history search to aggregate bilingual variants without affecting GitHub repo queries
- [x] Keep backfill snapshot/history collection consistent with the same bilingual variant logic
- [x] Add focused tests covering translated-variant fetch, merged visibility, and backfill consistency
- [x] Run focused verification
- [x] Commit this batch

## Notes

- Failing to translate must degrade back to the original query instead of breaking search
- The returned trend line and content must still come from real providers only
