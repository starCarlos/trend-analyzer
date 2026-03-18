# TrendScope 真实 Provider 验收记录模板

> 使用说明：
> 复制本文件，按一次真实联调验收填写一份记录。
> 也可以先运行 `scripts/init_real_provider_acceptance_record.py` 自动生成一份带日期和环境信息的记录文件。

## 1. 基本信息

- 验收日期：2026-03-18
- 验收人：admin_wsl
- 机器环境：sunjiaang
- 操作系统：Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39
- Python 解释器：/home/admin_wsl/sunnet/trend-analyzer/backend/.venv/bin/python
- 网络环境：
- 是否使用代理：是
- 验收模式：real

## 2. 配置摘要

- `PROVIDER_MODE`：real
- `GITHUB_API_BASE_URL`：https://api.github.com
- `NEWSNOW_BASE_URL`：https://newsnow.busiyi.world
- `NEWSNOW_SOURCE_IDS`：weibo,zhihu,bilibili,juejin,36kr,github
- `REQUEST_TIMEOUT_SECONDS`：8
- `SCHEDULER_ENABLED`：false

## 3. 本地验收前置结果

- 是否先运行 `scripts/local_acceptance.py`：`是`
- 命令：`backend/.venv/bin/python scripts/local_acceptance.py --base-url http://127.0.0.1:5060 --backend-python backend/.venv/bin/python --ui-python backend/.venv/bin/python --startup-timeout 30.0 --request-timeout 2.0 --json --skip-ui`
- 结果：`通过`
- 备注：[acceptance] Local acceptance passed

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

- GitHub 状态：success
- NewsNow 状态：success
- 是否通过：`通过`

原始输出摘录：

```text
{
  "probe_mode": "real",
  "requested_mode": "real",
  "effective_mode": "real",
  "summary": "real 模式在线探测成功，GitHub 和 NewsNow 都已返回响应。",
  "github": {
    "source": "github",
    "attempted_provider": "real",
    "status": "success",
    "endpoint": "https://api.github.com/rate_limit",
    "message": "GitHub 在线探测成功。rate limit remaining=55, limit=60."
  },
  "newsnow": {
    "source": "newsnow",
    "attempted_provider": "real",
    "status": "success",
    "endpoint": "https://newsnow.busiyi.world/api/s?id=weibo",
    "message": "NewsNow 在线探测成功。source_id=weibo, items=30."
  }
}
```

## 6. Smoke 总览结果

命令：

```bash
backend/.venv/bin/python -m app.cli provider-smoke openai/openai-python --period 30d --probe-mode real
```

如有强制搜索：

```bash
backend/.venv/bin/python -m app.cli provider-smoke openai/openai-python --period 30d --probe-mode real --force-search
```

结果摘要：

- summary：预检、在线探测和端到端搜索都已执行，当前 provider 冒烟通过。
- `search.status`：success
- `search.message`：端到端搜索执行成功。
- `next_steps`：接下来可在浏览器打开 /tracked 和搜索页，做人工联调验收。
- 是否通过：`通过`

原始输出摘录：

```text
{
  "query": "openai/openai-python",
  "period": "30d",
  "probe_mode": "real",
  "force_search": false,
  "summary": "预检、在线探测和端到端搜索都已执行，当前 provider 冒烟通过。",
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
    "summary": "real 模式在线探测成功，GitHub 和 NewsNow 都已返回响应。",
    "github": {
      "source": "github",
      "attempted_provider": "real",
      "status": "success",
      "endpoint": "https://api.github.com/rate_limit",
      "message": "GitHub 在线探测成功。rate limit remaining=55, limit=60."
    },
    "newsnow": {
      "source": "newsnow",
      "attempted_provider": "real",
      "status": "success",
      "endpoint": "https://newsnow.busiyi.world/api/s?id=weibo",
      "message": "NewsNow 在线探测成功。source_id=weibo, items=30."
    }
  },
  "search": {
    "query": "openai/openai-python",
    "period": "30d",
    "status": "success",
    "message": "端到端搜索执行成功。",
    "keyword_kind": "github_repo",
    "normalized_query": "openai/openai-python",
    "trend_series_count": 2,
    "content_item_count": 20,
    "availability": {
      "github_history": "ready",
      "newsnow_snapshot": "ready"
    },
    "backfill_status": "success"
  },
  "next_steps": [
    "接下来可在浏览器打开 /tracked 和搜索页，做人工联调验收。"
  ]
}
```

## 7. 页面人工验收

### 7.1 GitHub 项目搜索

- 验证地址：http://127.0.0.1:5060/?q=openai%2Fopenai-python&period=30d
- 是否可打开：`是`
- 是否看到今日快照：`是`
- 是否看到 GitHub 内容流：`是`
- 是否看到趋势图：`是`
- `Track/Untrack` 是否正常：`是`
- 截图路径：/tmp/trendscope-real-acceptance-5060/trendscope-search-smoke-evidence.json
- 备注：自动页面验收使用 inprocess driver；结果按回填完成后的页面状态判定；当前环境未生成浏览器截图；证据文件：/tmp/trendscope-real-acceptance-5060/trendscope-search-smoke-evidence.json

### 7.2 普通关键词搜索

- 验证地址：http://127.0.0.1:5060/?q=mcp&period=30d
- 是否看到 NewsNow 快照：`是`
- 是否看到内容列表：`是`
- 是否看到累计提示或累计曲线：`是`
- 截图路径：/tmp/trendscope-real-acceptance-5060/trendscope-keyword-smoke-evidence.json
- 备注：自动页面验收使用 inprocess driver；结果按回填完成后的页面状态判定；当前环境未生成浏览器截图；证据文件：/tmp/trendscope-real-acceptance-5060/trendscope-keyword-smoke-evidence.json

### 7.3 `/tracked` 页

- 是否可打开：`是`
- `Verify real` 是否正常：`是`
- `Run smoke` 是否正常：`是`
- 是否看到 collect runs：`是`
- 截图路径：/tmp/trendscope-real-acceptance-5060/trendscope-tracked-smoke-evidence.json
- 备注：Triggered 1 collection run(s). Inprocess 取证仅重放当前 repo query，避免全量 tracked collection 拖慢验收。；自动页面验收使用 inprocess driver；结果按回填完成后的页面状态判定；当前环境未生成浏览器截图；证据文件：/tmp/trendscope-real-acceptance-5060/trendscope-tracked-smoke-evidence.json

### 7.4 补充回归：裸仓库名搜索

- 验证地址：http://127.0.0.1:5060/?q=openclaw&period=30d
- 是否自动识别为 GitHub repository：`是`
- 规范化结果是否为 `openclaw/openclaw`：`是`
- 是否看到 GitHub 内容流：`是`
- 是否看到趋势图：`是`
- 补充证据：`GET /api/search?q=openclaw&period=30d` 返回 `keyword.kind=github_repo`
- 取证路径：/tmp/trendscope-openclaw-ui-smoke.json
- 备注：这是补充搜索体验回归，不属于原始 PRD 验收项；本次使用 inprocess UI smoke 验证裸仓库名会自动提升成真实 GitHub 仓库查询。

## 8. 追踪与采集结果

- 是否验证 `Collect tracked`：`是`
- 是否验证 scheduler：未自动验证
- collect runs 是否新增：`否`
- 是否观察到新点位或更新时间变化：未自动验证
- 备注：Triggered 1 collection run(s). Inprocess 取证仅重放当前 repo query，避免全量 tracked collection 拖慢验收。

## 9. PRD 验收项映射

| 项目 | 结果 | 备注 |
|---|---|---|
| 可以从空库启动 | 通过 | 临时空库启动成功；db=/tmp/trendscope-empty-startup-abedabb6b0974a43bf8d922ab61080d7.db；health.env=empty_db_probe；provider_mode=mock |
| GitHub 项目首次搜索能完成冷启动并看到历史图 | 通过 | 搜索页关键元素齐全，Track/Untrack 可切换。 |
| 普通关键词首次搜索能看到 NewsNow 快照和内容列表 | 通过 | 普通关键词搜索页关键元素齐全。 |
| 加入追踪后，定时任务能持续写入新点位 | 部分通过 | 已自动触发 `Collect tracked`，但本次未观察到新增 collect runs；scheduler 持续写入仍需人工观察。 |
| 搜索、回填、采集失败都有可读错误状态 | 部分通过 | 已自动验证 provider 配置缺失和在线探测跳过文案可读；search/backfill/collect 失败仍需人工构造。 |

## 10. 最终结论

- 本次真实 provider 联调结果：`部分通过`
- 是否允许继续上线前步骤：`是`
- 阻塞项：
- 后续动作：scheduler 持续采集仍需人工观察。；失败场景可读性仍需人工构造验证。
