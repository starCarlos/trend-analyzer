# Archive Relevance Config Checklist (2026-03-19)

## Goal

Expose archive relevance tuning in user-facing env templates and runtime docs, without changing runtime behavior.

## Checklist

- [x] Confirm runtime config keys in `backend/app/config.py`
- [x] Align `FRONTEND_ORIGIN` examples with current default port `5081`
- [x] Align `NEWSNOW_SOURCE_IDS` examples with the current canonical source ids
- [x] Expose archive provider env keys in all env template files
- [x] Expose `ARCHIVE_AMBIGUOUS_QUERY_CONTEXTS_JSON` in docs and explain its purpose
- [x] Run focused verification on config/doc consistency
- [x] Commit this batch without `test-results/`

## Notes

- Canonical `NEWSNOW_SOURCE_IDS` values are `weibo,zhihu,bilibili,juejin,36kr,github`
- Legacy ids like `weibo-hot` and `github-trending` remain compatibility aliases, but should not be shown as the primary examples
- Focused verification used:
  - `backend/.venv/bin/python -m py_compile backend/app/config.py backend/app/services/archive_relevance.py backend/app/services/providers.py backend/app/services/search.py`
  - `Settings(_env_file=...)` loads for all three example env files
