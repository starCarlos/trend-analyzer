# 2026-03-17 Real Acceptance Handoff

## 1. 先读这些文件

- `docs/acceptance-records/2026-03-17-real-provider-acceptance.md`
- `scripts/ui_smoke_test.py`
- `scripts/update_real_provider_acceptance_record.py`
- `backend/tests/test_acceptance_scripts.py`
- `backend/app/services/search.py`
- `backend/app/services/collector.py`
- `backend/tests/test_services.py`

## 2. 当前状态

- 今天这轮真实 provider 验收已经继续跑完，结果已写回 `docs/acceptance-records/2026-03-17-real-provider-acceptance.md`
- 页面验收不再依赖 Playwright/Chromium 才能继续
- `scripts/ui_smoke_test.py` 已新增 `--driver inprocess`
- `scripts/ui_smoke_test.py --driver inprocess` 现在会按“回填完成后的页面状态”取证，不再只看第一次空响应
- `scripts/update_real_provider_acceptance_record.py` 已支持把 inprocess 证据和备注写回验收记录
- `backend/app/services/search.py` 已修复失败 backfill 被下一次搜索立刻重建成 `pending` 的问题；普通搜索默认保留 `failed/partial`，显式 refresh/collect 才会重试
- 回归测试已通过：
  - `backend/.venv/bin/python -m unittest backend.tests.test_acceptance_scripts -v`
  - `backend/.venv/bin/python -m unittest backend.tests.test_services.ServiceTestCase.test_search_reuses_failed_backfill_until_explicit_retry backend.tests.test_services.ServiceTestCase.test_refresh_keyword_retries_failed_backfill_explicitly backend.tests.test_acceptance_scripts -v`

## 3. 当前真实阻塞

- 当前环境外网访问被拒绝
- `provider-verify --probe-mode real` 仍失败
- 失败信息是：
  - GitHub: `Network error: [Errno 1] Operation not permitted`
  - NewsNow: `Network error: [Errno 1] Operation not permitted`
- 因为在线探测失败，`provider-smoke` 默认跳过真实搜索，当前记录中的 smoke 仍是失败
- 页面内容缺口现在可以直接归因到真实 provider 网络失败，不再是 inprocess 验收脚本没有模拟轮询导致的假阴性

## 4. 页面验收结论

- GitHub 项目搜索页：
  - 可打开
  - 今日快照可见
  - 趋势图可见
  - `Track/Untrack` 正常
  - GitHub 内容流未看到
  - 新证据已明确写出 `github/content` 和 `newsnow/snapshot` 的网络失败摘要
- 普通关键词搜索页：
  - 可打开
  - NewsNow 快照可见
  - 累计提示可见
  - 内容列表未看到
  - 新证据已明确写出 `newsnow/snapshot` 的网络失败摘要
- `/tracked` 页：
  - 可打开
  - `Verify real` 正常
  - `Run smoke` 正常
  - `Collect tracked` 已触发
  - collect runs 有新增

## 5. 证据文件

- `/tmp/trendscope-real-acceptance/trendscope-search-smoke-evidence.json`
- `/tmp/trendscope-real-acceptance/trendscope-keyword-smoke-evidence.json`
- `/tmp/trendscope-real-acceptance/trendscope-tracked-smoke-evidence.json`
- `/tmp/trendscope-real-acceptance/latest-ui-smoke.json`

## 6. 复跑命令

重新写回今天这份记录：

```bash
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py \
  --record docs/acceptance-records/2026-03-17-real-provider-acceptance.md \
  --mode real \
  --run-ui \
  --ui-python backend/.venv/bin/python \
  --screenshots-dir /tmp/trendscope-real-acceptance
```

单独跑页面验收降级链路：

```bash
backend/.venv/bin/python scripts/ui_smoke_test.py \
  --driver inprocess \
  --output-dir /tmp/trendscope-real-acceptance
```

回归当前脚本测试：

```bash
backend/.venv/bin/python -m unittest backend.tests.test_acceptance_scripts -v
```

回归搜索失败态与显式重试逻辑：

```bash
backend/.venv/bin/python -m unittest \
  backend.tests.test_services.ServiceTestCase.test_search_reuses_failed_backfill_until_explicit_retry \
  backend.tests.test_services.ServiceTestCase.test_refresh_keyword_retries_failed_backfill_explicitly \
  backend.tests.test_acceptance_scripts -v
```

## 7. 下个会话建议动作

- 如果新环境可联网，先重跑：
  - `backend/.venv/bin/python -m app.cli provider-verify --probe-mode real`
  - `backend/.venv/bin/python -m app.cli provider-smoke anthropic/claude-code --period 30d --probe-mode real`
- 如果 `provider-verify` 转为成功，再重写验收记录
- 如果联网后关键词页仍没有内容列表，优先检查：
  - `backend/app/services/providers.py`
  - `backend/app/services/backfill.py`
  - `backend/app/services/search.py`
- 如果仍是当前受限环境，页面内容缺口默认视为真实 provider 网络失败，不要再怀疑失败态被新 `pending` job 冲掉
- 如果要继续沿用当前受限环境，默认使用 `--driver inprocess`，不要再把问题归因到 Playwright sandbox

## 8. 给新会话的最短上下文

可以直接告诉新会话：

> 继续处理 `docs/acceptance-records/2026-03-17-real-provider-acceptance-handoff.md` 里的真实 provider 验收续跑事项。当前浏览器验收已改成 `scripts/ui_smoke_test.py --driver inprocess`，剩余阻塞是外网 `Operation not permitted` 和页面数据缺口，不是 Playwright 启动失败。
