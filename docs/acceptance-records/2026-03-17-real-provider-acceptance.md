# TrendScope 真实 Provider 验收记录模板

> 使用说明：
> 复制本文件，按一次真实联调验收填写一份记录。
> 也可以先运行 `scripts/init_real_provider_acceptance_record.py` 自动生成一份带日期和环境信息的记录文件。

## 1. 基本信息

- 验收日期：2026-03-17
- 验收人：
- 机器环境：
- 操作系统：Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39
- Python 解释器：/home/admin_wsl/sunnet/trend-analyzer/backend/.venv/bin/python
- 网络环境：
- 是否使用代理：
- 验收模式：real

## 2. 配置摘要

- `PROVIDER_MODE`：real
- `GITHUB_API_BASE_URL`：https://api.github.com
- `NEWSNOW_BASE_URL`：https://newsnow.busiyi.world
- `NEWSNOW_SOURCE_IDS`：weibo-hot,zhihu-hot,bilibili-hot,juejin-hot,36kr-hot,github-trending
- `REQUEST_TIMEOUT_SECONDS`：8
- `SCHEDULER_ENABLED`：false

## 3. 本地验收前置结果

- 是否先运行 `scripts/local_acceptance.py`：`是`
- 命令：`backend/.venv/bin/python scripts/local_acceptance.py --base-url http://127.0.0.1:8000 --backend-python backend/.venv/bin/python --ui-python /usr/bin/python3 --startup-timeout 30.0 --request-timeout 2.0 --json --skip-ui`
- 结果：`通过`
- 备注：health.env=probe_blocked；provider_mode=unknown；tests=是；ui=否；backend_already_running=否；backend_auto_started=是

## 4. Provider 预检结果

命令：

```bash
backend/.venv/bin/python -m app.cli provider-status
```

结果摘要：

- `requested_mode`：real
- `resolved_provider`：real
- GitHub 状态：warning
- NewsNow 状态：ready
- 是否通过：`通过`

原始输出摘录：

```text
{
  "requested_mode": "real",
  "resolved_provider": "real",
  "summary": "当前是 real 模式，本地配置看起来可用，但网络连通性和真实返回结果尚未验证。",
  "github": {
    "source": "github",
    "mode": "real",
    "preferred_provider": "real",
    "fallback_provider": null,
    "status": "warning",
    "can_use_real_provider": true,
    "issues": [],
    "notes": [
      "GitHub 真实配置在本地看起来可用，但当前还没有在线验证网络连通性。",
      "GITHUB_TOKEN 为空，真实请求可用但更容易触发限流。",
      "HTTP_PROXY 已配置，真实请求会经过代理。"
    ]
  },
  "newsnow": {
    "source": "newsnow",
    "mode": "real",
    "preferred_provider": "real",
    "fallback_provider": null,
    "status": "ready",
    "can_use_real_provider": true,
    "issues": [],
    "notes": [
      "NewsNow 真实配置在本地看起来可用，但当前还没有在线验证网络连通性。",
      "NEWSNOW_SOURCE_IDS 当前包含 6 个 source id。",
      "HTTP_PROXY 已配置，真实请求会经过代理。"
    ]
  }
}
```

## 5. 在线探测结果

命令：

```bash
backend/.venv/bin/python -m app.cli provider-verify --probe-mode real
```

结果摘要：

- GitHub 状态：failed
- NewsNow 状态：failed
- 是否通过：`失败`

原始输出摘录：

```text
{
  "probe_mode": "real",
  "requested_mode": "real",
  "effective_mode": "real",
  "summary": "real 模式在线探测已执行，但至少有一个数据源失败。",
  "github": {
    "source": "github",
    "attempted_provider": "real",
    "status": "failed",
    "endpoint": "https://api.github.com/rate_limit",
    "message": "GitHub 在线探测失败: Network error: [Errno 1] Operation not permitted"
  },
  "newsnow": {
    "source": "newsnow",
    "attempted_provider": "real",
    "status": "failed",
    "endpoint": "https://newsnow.busiyi.world/api/s/weibo-hot",
    "message": "NewsNow 在线探测失败: Network error: [Errno 1] Operation not permitted"
  }
}
```

## 6. Smoke 总览结果

命令：

```bash
backend/.venv/bin/python -m app.cli provider-smoke anthropic/claude-code --period 30d --probe-mode real
```

如有强制搜索：

```bash
backend/.venv/bin/python -m app.cli provider-smoke anthropic/claude-code --probe-mode real --force-search
```

结果摘要：

- summary：在线探测未全部成功，端到端搜索已按默认策略跳过。
- `search.status`：skipped
- `search.message`：在线探测没有全部成功，默认跳过真实搜索。需要强制执行时使用 force_search=true。
- `next_steps`：先处理 GitHub 在线探测失败或跳过，再做真实联调。；先处理 NewsNow 在线探测失败或跳过，再做真实联调。；如果你仍想强制验证真实搜索，重新运行 provider-smoke 并开启 force_search。
- 是否通过：`失败`

原始输出摘录：

```text
{
  "query": "anthropic/claude-code",
  "period": "30d",
  "probe_mode": "real",
  "force_search": false,
  "summary": "在线探测未全部成功，端到端搜索已按默认策略跳过。",
  "provider_status": {
    "requested_mode": "real",
    "resolved_provider": "real",
    "summary": "当前是 real 模式，本地配置看起来可用，但网络连通性和真实返回结果尚未验证。",
    "github": {
      "source": "github",
      "mode": "real",
      "preferred_provider": "real",
      "fallback_provider": null,
      "status": "warning",
      "can_use_real_provider": true,
      "issues": [],
      "notes": [
        "GitHub 真实配置在本地看起来可用，但当前还没有在线验证网络连通性。",
        "GITHUB_TOKEN 为空，真实请求可用但更容易触发限流。",
        "HTTP_PROXY 已配置，真实请求会经过代理。"
      ]
    },
    "newsnow": {
      "source": "newsnow",
      "mode": "real",
      "preferred_provider": "real",
      "fallback_provider": null,
      "status": "ready",
      "can_use_real_provider": true,
      "issues": [],
      "notes": [
        "NewsNow 真实配置在本地看起来可用，但当前还没有在线验证网络连通性。",
        "NEWSNOW_SOURCE_IDS 当前包含 6 个 source id。",
        "HTTP_PROXY 已配置，真实请求会经过代理。"
      ]
    }
  },
  "provider_verify": {
    "probe_mode": "real",
    "requested_mode": "real",
    "effective_mode": "real",
    "summary": "real 模式在线探测已执行，但至少有一个数据源失败。",
    "github": {
      "source": "github",
      "attempted_provider": "real",
      "status": "failed",
      "endpoint": "https://api.github.com/rate_limit",
      "message": "GitHub 在线探测失败: Network error: [Errno 1] Operation not permitted"
    },
    "newsnow": {
      "source": "newsnow",
      "attempted_provider": "real",
      "status": "failed",
      "endpoint": "https://newsnow.busiyi.world/api/s/weibo-hot",
      "message": "NewsNow 在线探测失败: Network error: [Errno 1] Operation not permitted"
    }
  },
  "search": {
    "query": "anthropic/claude-code",
    "period": "30d",
    "status": "skipped",
    "message": "在线探测没有全部成功，默认跳过真实搜索。需要强制执行时使用 force_search=true。",
    "keyword_kind": null,
    "normalized_query": null,
    "trend_series_count": 0,
    "content_item_count": 0,
    "availability": {},
    "backfill_status": null
  },
  "next_steps": [
    "先处理 GitHub 在线探测失败或跳过，再做真实联调。",
    "先处理 NewsNow 在线探测失败或跳过，再做真实联调。",
    "如果你仍想强制验证真实搜索，重新运行 provider-smoke 并开启 force_search。"
  ]
}
```

## 7. 页面人工验收

### 7.1 GitHub 项目搜索

- 验证地址：http://127.0.0.1:8000/?q=anthropic%2Fclaude-code&period=30d
- 是否可打开：`是`
- 是否看到今日快照：`是`
- 是否看到 GitHub 内容流：`否`
- 是否看到趋势图：`是`
- `Track/Untrack` 是否正常：`是`
- 截图路径：/tmp/trendscope-real-acceptance/trendscope-search-smoke-evidence.json
- 备注：自动页面验收使用 inprocess driver；结果按回填完成后的页面状态判定；当前环境未生成浏览器截图；证据文件：/tmp/trendscope-real-acceptance/trendscope-search-smoke-evidence.json；回填失败摘要：github/content: Network error for https://api.github.com/repos/anthropic/claude-code/releases?per_page=6: [Errno 1] Operation not permitted；newsnow/snapshot: Network error for https://newsnow.busiyi.world/api/s/weibo-hot: [Errno 1] Operation not permitted

### 7.2 普通关键词搜索

- 验证地址：http://127.0.0.1:8000/?q=mcp&period=30d
- 是否看到 NewsNow 快照：`是`
- 是否看到内容列表：`否`
- 是否看到累计提示或累计曲线：`是`
- 截图路径：/tmp/trendscope-real-acceptance/trendscope-keyword-smoke-evidence.json
- 备注：自动页面验收使用 inprocess driver；结果按回填完成后的页面状态判定；当前环境未生成浏览器截图；证据文件：/tmp/trendscope-real-acceptance/trendscope-keyword-smoke-evidence.json；回填失败摘要：newsnow/snapshot: Network error for https://newsnow.busiyi.world/api/s/weibo-hot: [Errno 1] Operation not permitted

### 7.3 `/tracked` 页

- 是否可打开：`是`
- `Verify real` 是否正常：`是`
- `Run smoke` 是否正常：`是`
- 是否看到 collect runs：`是`
- 截图路径：/tmp/trendscope-real-acceptance/trendscope-tracked-smoke-evidence.json
- 备注：Triggered 83 collection run(s).；自动页面验收使用 inprocess driver；结果按回填完成后的页面状态判定；当前环境未生成浏览器截图；证据文件：/tmp/trendscope-real-acceptance/trendscope-tracked-smoke-evidence.json

## 8. 追踪与采集结果

- 是否验证 `Collect tracked`：`是`
- 是否验证 scheduler：未自动验证
- collect runs 是否新增：`是`
- 是否观察到新点位或更新时间变化：未自动验证
- 备注：Triggered 83 collection run(s).

## 9. PRD 验收项映射

| 项目 | 结果 | 备注 |
|---|---|---|
| 可以从空库启动 | 通过 | 临时空库启动成功；db=/tmp/trendscope-empty-startup-2704ee8b1c264b94bd665fb3078c5db1.db；health.env=probe_blocked；provider_mode=unknown |
| GitHub 项目首次搜索能完成冷启动并看到历史图 | 失败 | 未看到 GitHub 内容流；provider smoke 搜索未通过，需先修复 CLI 链路。 |
| 普通关键词首次搜索能看到 NewsNow 快照和内容列表 | 失败 | 未看到内容列表；provider smoke 搜索未通过，需先修复 CLI 链路。 |
| 加入追踪后，定时任务能持续写入新点位 | 部分通过 | 已自动验证 `Collect tracked`，collect runs 有新增；scheduler 持续写入仍需人工观察。 |
| 搜索、回填、采集失败都有可读错误状态 | 部分通过 | 已自动验证 provider 配置缺失和在线探测跳过文案可读；search/backfill/collect 失败仍需人工构造。 |

## 10. 最终结论

- 本次真实 provider 联调结果：`失败`
- 是否允许继续上线前步骤：`否`
- 阻塞项：在线探测未通过。；Smoke 总览未通过。；GitHub 项目搜索页未通过。；普通关键词搜索页未通过。
- 后续动作：scheduler 持续采集仍需人工观察。；失败场景可读性仍需人工构造验证。
