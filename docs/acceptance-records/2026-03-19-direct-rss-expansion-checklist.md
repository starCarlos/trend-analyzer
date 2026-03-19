# 2026-03-19 Direct RSS Expansion Checklist

- [completed] Expand the built-in no-login RSS catalog with a few high-signal tech feeds.
- [completed] Make extra Direct RSS feeds configurable without code changes.
- [completed] Prefer language-matched feed ordering and run focused verification.

Verification:
- Confirmed public feed payloads for `InfoQ`, `IT Home`, and `Leiphone`.
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_direct_rss_catalog_appends_extra_feeds`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_direct_rss_feed_order_prefers_zh_sources_for_cjk_queries`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_real_provider_fetch_direct_rss_archive_parses_rss_and_atom_feeds`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_keyword_search_prefetches_direct_rss_inline_on_first_lookup`
- `./.venv/bin/python -m compileall app/services app/schemas.py`
- Live request: `GET /api/provider-status`
- Live request: `GET /api/search?q=claude&period=30d`
