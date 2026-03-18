# 2026-03-18 GDELT Quality Checklist

- [x] Tighten GDELT relevance filtering for query/title/url matching
- [x] Deduplicate near-identical GDELT articles before storing them
- [x] Add focused tests for noisy and duplicate GDELT results
- [x] Verify the live `openclaw` query returns cleaner GDELT-backed content

## Notes

- `backend/tests/test_services.py` covers domain-only false positives, near-duplicate title dedupe, inline GDELT history prefetch, and read-path filtering for previously stored noisy items.
- Live validation on `2026-03-18` confirmed `RealDataProvider.fetch_gdelt_archive("openclaw")` now returns a smaller, cleaner set than the earlier noisy payloads; `/api/search?q=openclaw&period=30d&content_source=gdelt` also rebuilds the displayed GDELT timeline from filtered items instead of stale stored counts.
