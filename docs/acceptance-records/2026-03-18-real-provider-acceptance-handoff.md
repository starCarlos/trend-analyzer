# 2026-03-18 Real Acceptance Handoff

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

## 4. 现在剩下的事情

唯一还没完成的是：

- 重新生成并写回 2026-03-18 这份真实 provider 验收记录

原因：

- 之前第一次跑 `scripts/update_real_provider_acceptance_record.py` 时，被本地空库 health probe 的代理问题打断
- 这个问题已经修好
- 还没重新执行一次最终写回命令

## 5. 直接复跑命令

先回到仓库根目录：

```bash
cd /home/admin_wsl/sunnet/trend-analyzer
```

重新写回今天的记录：

```bash
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py \
  --record docs/acceptance-records/2026-03-18-real-provider-acceptance.md \
  --mode real \
  --run-ui \
  --ui-python backend/.venv/bin/python \
  --screenshots-dir /tmp/trendscope-real-acceptance
```

如果想先单独确认 CLI 结果：

```bash
cd /home/admin_wsl/sunnet/trend-analyzer/backend
.venv/bin/python -m app.cli provider-verify --probe-mode real
.venv/bin/python -m app.cli provider-smoke anthropic/claude-code --period 30d --probe-mode real
```

## 6. 当前测试状态

以下测试已通过：

```bash
cd /home/admin_wsl/sunnet/trend-analyzer
backend/.venv/bin/python -m unittest backend.tests.test_services -v
backend/.venv/bin/python -m unittest backend.tests.test_acceptance_scripts -v
```

## 7. 对新会话最短说明

可以直接告诉新会话：

> 继续处理 `docs/acceptance-records/2026-03-18-real-provider-acceptance-handoff.md`。2026-03-18 用户自己终端里的 `provider-verify` 和 `provider-smoke` 已经成功。NewsNow 接口路径、source id、代理下本地 health probe 的问题都已经修过了。当前只差重跑 `scripts/update_real_provider_acceptance_record.py`，把 `docs/acceptance-records/2026-03-18-real-provider-acceptance.md` 正式写完。
