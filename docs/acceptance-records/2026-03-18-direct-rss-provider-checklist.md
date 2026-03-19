# 2026-03-18 Direct RSS Provider Checklist

- [completed] Add a no-login `direct_rss` archive provider backed by public RSS feeds.
- [completed] Wire `direct_rss` into archive prefetch, backfill, availability, diagnostics, verification, and UI labels.
- [completed] Add focused tests for feed parsing and first-search history availability.

Verification:
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_real_provider_fetch_direct_rss_archive_parses_rss_and_atom_feeds`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_keyword_search_prefetches_direct_rss_inline_on_first_lookup`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_provider_status_reports_mock_mode`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_real_provider_fetch_google_news_archive_parses_and_filters_feed`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_real_provider_fetch_gdelt_archive_parses_and_filters_response`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_keyword_search_prefetches_history_inline_on_first_lookup`
- `./.venv/bin/python -m unittest tests.test_services.ServiceTestCase.test_keyword_search_prefetches_gdelt_inline_on_first_lookup`
- `./.venv/bin/python -m compileall app/services app/schemas.py`
