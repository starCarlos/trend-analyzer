# 2026-03-18 Real Acceptance Handoff

> Public-repo note:
> local absolute paths and stale local ports were normalized in this copy.

## 1. 先读这些文件

- `docs/acceptance-records/2026-03-18-real-provider-acceptance.md`
- `docs/acceptance-records/2026-03-17-real-provider-acceptance-handoff.md`
- `backend/app/services/provider_urls.py`
- `backend/app/services/provider_verification.py`
- `backend/app/services/providers.py`
- `scripts/local_acceptance.py`
- `scripts/update_real_provider_acceptance_record.py`
- `backend/tests/test_services.py`
- `backend/tests/test_acceptance_scripts.py`

## 2. 当前状态

- 2026-03-18 在用户自己的终端里，真实 provider 已经从失败恢复到可用
- `docs/acceptance-records/2026-03-18-real-provider-acceptance.md` 已重新写回并补全
- `TRENDSCOPE_UI_DRIVER=inprocess backend/.venv/bin/python scripts/local_acceptance.py --require-running --json` 已通过
  - `status=passed`
  - `provider_mode=real`
- 已补做两类临时 probe 验证
  - `scheduler_probe`：验证 tracked 关键词会被 scheduler 自动触发采集，并写入 success `collect_runs`
  - `failure_probe`：验证 `search / backfill / collect` 失败时，API 返回和 `collect_logs` 都有可读错误信息
- `provider-verify --probe-mode real` 已成功
  - GitHub: success
  - NewsNow: success
- `provider-smoke anthropic/claude-code --period 30d --probe-mode real` 已成功
  - `search.status=success`
  - `trend_series_count=2`
  - `content_item_count=4`
  - `availability.github_history=ready`
  - `availability.newsnow_snapshot=ready`
- 当前 `provider-smoke` 里 `backfill_status=partial`
  - 这不是当前阻塞项
  - 真实 provider smoke 已判定通过
- 裸仓库名 `openclaw` 现已能自动解析为 GitHub repository
  - `GET /api/search?q=openclaw&period=30d`
  - `keyword.kind=github_repo`
  - `normalized_query=openclaw/openclaw`
  - GitHub 历史与内容流均已返回

## 3. 本轮已完成的修复

### 3.1 NewsNow 真实接口修复

- 已确认当前 NewsNow 真实接口优先走：
  - `/api/s?id=<source_id>`
- 旧路径仍兼容回退：
  - `/api/s/<source_id>`
- 已把请求头改成浏览器 UA，而不是 `TrendScope/0.1`

相关文件：

- `backend/app/services/provider_urls.py`
- `backend/app/services/provider_verification.py`
- `backend/app/services/providers.py`

### 3.2 NewsNow source id 修复

- 旧配置里的 source id 已过期
  - `weibo-hot`
  - `zhihu-hot`
  - `bilibili-hot`
  - `juejin-hot`
  - `36kr-hot`
  - `github-trending`
- 当前默认配置已改成新的 source id
  - `weibo,zhihu,bilibili,juejin,36kr,github`
- 同时保留旧 id 到新 id 的兼容映射
  - `weibo-hot -> weibo`
  - `github-trending -> github`
  - 其他几个 `*-hot` 同理

相关文件：

- `backend/app/config.py`
- `backend/.env`
- `backend/app/services/provider_urls.py`

### 3.3 inprocess UI 验收修复

- `scripts/ui_smoke_test.py --driver inprocess` 现在按“回填完成后的页面状态”取证
- 不再只看第一次空响应
- 证据文件里会写回 backfill 失败摘要

### 3.4 搜索失败态保留修复

- 普通搜索不再把最近一次 `failed/partial` job 立刻覆盖成新的 `pending`
- 显式 refresh / collect 才会重试失败 backfill

相关文件：

- `backend/app/services/search.py`
- `backend/app/services/collector.py`

### 3.5 验收记录脚本本地 health probe 修复

- `scripts/update_real_provider_acceptance_record.py` 里的空库启动校验会调用 `scripts/local_acceptance.py`
- 之前本地 `127.0.0.1` health probe 可能被代理干扰
- 现在 loopback / localhost 探测会强制直连，不走代理

相关文件：

- `scripts/local_acceptance.py`

### 3.6 裸仓库名自动解析修复

- 搜索输入现在除了 GitHub URL 和 `owner/repo` 之外，还会对看起来像仓库名的单词做 GitHub 解析补充
- 当 GitHub 搜索结果里存在稳定目标时，会把裸名称提升成真实仓库
  - 当前已验证：`openclaw -> openclaw/openclaw`
- 解析策略仍保持保守
  - 只有在结果足够明确时才会提升
  - 如果无法稳定判定，仍保留为普通关键词
- `openclaw` 的接口与 inprocess UI smoke 均已验证通过

相关文件：

- `backend/app/services/query_parser.py`
- `backend/app/services/github_repo_resolution.py`
- `backend/app/services/search.py`
- `backend/tests/test_services.py`
- `docs/current-functional-flow.md`
- `docs/mvp-completion-checklist.md`

## 4. 现在剩下的事情

当前没有新的阻塞性待办，也没有未收口的 PRD 验收项。

如果还要继续补强，优先顺序如下：

- 人工用浏览器继续观察 `/tracked` 页上的 scheduler 长时间运行表现
- 如果后续继续改搜索体验，记得同步更新 `docs/current-functional-flow.md`

## 5. 直接复跑命令

先回到仓库根目录：

```bash
cd <repo-root>
```

重新写回 2026-03-18 验收记录：

```bash
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py \
  --record docs/acceptance-records/2026-03-18-real-provider-acceptance.md \
  --mode real \
  --run-ui \
  --ui-python backend/.venv/bin/python \
  --screenshots-dir /tmp/trendscope-real-acceptance
```

如果想先单独确认 CLI 与补充回归结果：

```bash
cd backend
.venv/bin/python -m app.cli provider-verify --probe-mode real
.venv/bin/python -m app.cli provider-smoke anthropic/claude-code --period 30d --probe-mode real
```

补充检查裸仓库名解析：

```bash
curl --noproxy '*' -fsS 'http://127.0.0.1:5081/api/search?q=openclaw&period=30d'
backend/.venv/bin/python scripts/ui_smoke_test.py \
  --driver inprocess \
  --base-url http://127.0.0.1:5081 \
  --repo-query openclaw \
  --keyword-query mcp \
  --output-json /tmp/trendscope-openclaw-ui-smoke.json
```

补充做工程验证 probe：

```bash
HOST=127.0.0.1 PORT=5061 RELOAD=0 APP_ENV=scheduler_probe PROVIDER_MODE=real \
DATABASE_URL=sqlite:////tmp/trendscope-scheduler-check.db \
SCHEDULER_ENABLED=1 SCHEDULER_INTERVAL_SECONDS=5 SCHEDULER_INITIAL_DELAY_SECONDS=1 \
backend/.venv/bin/python backend/run_server.py

HOST=127.0.0.1 PORT=5062 RELOAD=0 APP_ENV=failure_probe PROVIDER_MODE=real \
DATABASE_URL=sqlite:////tmp/trendscope-failure-check.db \
NEWSNOW_BASE_URL=http://127.0.0.1:9 REQUEST_TIMEOUT_SECONDS=1 \
backend/.venv/bin/python backend/run_server.py
```

## 6. 当前测试状态

以下测试已通过：

```bash
cd <repo-root>
backend/.venv/bin/python -m unittest backend.tests.test_services -v
backend/.venv/bin/python -m unittest backend.tests.test_acceptance_scripts -v
```

## 7. 对新会话最短说明

可以直接告诉新会话：

> 继续处理 `docs/acceptance-records/2026-03-18-real-provider-acceptance-handoff.md`。2026-03-18 的真实 provider 验收记录已经写回，`local_acceptance` 已通过，NewsNow 接口路径、source id、代理下本地 health probe 的问题都已经修过了。额外完成了两类补充验证：裸仓库名 `openclaw` 现在会自动解析成 `openclaw/openclaw`，接口和 UI smoke 已通过；`scheduler_probe` 和 `failure_probe` 已分别验证 scheduler 自动采集以及 `search/backfill/collect` 失败态的可读性。当前没有新的阻塞项，后续只剩可选的人眼长期观察。
