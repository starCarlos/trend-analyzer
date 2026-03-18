# TrendScope 当前功能流程

> 基于当前代码实现整理，而不是基于 PRD 目标态整理。
> 更新时间：2026-03-17

## 1. 文档目的

这份文档描述当前仓库里已经实现的完整功能流程，包括：

- 后端 API 的实际入口和处理顺序
- CLI 的可用命令和它们走的服务路径
- 前端搜索页当前能完成的交互
- 数据如何写入 SQLite
- 当前实现边界和已知限制

本文只描述代码里真实存在的能力，不描述尚未落地的计划功能。

## 2. 当前系统组成

当前仓库由三部分组成：

- `backend/`
  FastAPI 后端、SQLite 数据模型、provider 切换、回填与采集服务、CLI、静态网页
- `frontend/`
  历史 Next.js 原型，当前默认运行链路不依赖它
- `docs/`
  产品、技术、计划和当前实现说明文档

## 3. 当前可用入口

### 3.1 HTTP API

当前后端暴露以下接口：

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/search` | 搜索一个 repository 或普通关键词，可附带 `content_source` 过滤内容流 |
| `GET` | `/api/keywords/{keyword_id}/backfill-status` | 查询异步回填任务状态 |
| `GET` | `/api/keywords` | 列出关键词 |
| `POST` | `/api/keywords` | 创建关键词并可选触发回填/追踪 |
| `POST` | `/api/keywords/{keyword_id}/track` | 标记为追踪 |
| `DELETE` | `/api/keywords/{keyword_id}/track` | 取消追踪 |
| `POST` | `/api/collect/trigger` | 手动触发采集 |
| `GET` | `/api/collect/status` | 查询自动采集调度器状态 |
| `GET` | `/api/collect/logs` | 查询采集日志 |
| `GET` | `/api/provider-status` | 查询 provider 本地预检结果 |
| `POST` | `/api/provider-verify` | 发起 provider 轻量在线探测 |
| `POST` | `/api/provider-smoke` | 运行 provider 预检、在线探测和可选的端到端搜索 smoke |

此外，后端还直接提供：

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/` | 返回当前搜索网页 |
| `GET` | `/tracked` | 返回当前追踪列表页 |
| `GET` | `/assets/*` | 返回网页静态资源 |

### 3.2 CLI

当前 CLI 入口是 `backend/app/cli.py`，已实现命令：

| 命令 | 作用 |
|---|---|
| `python -m app.cli health` | 输出健康状态 |
| `python -m app.cli search <query>` | 运行一次搜索，可同步执行回填 |
| `python -m app.cli track <query>` | 搜索并标记为追踪 |
| `python -m app.cli list-tracked` | 列出追踪中的关键词 |
| `python -m app.cli scheduler-status` | 查看自动采集调度器状态 |
| `python -m app.cli provider-status` | 查看 provider 本地预检结果 |
| `python -m app.cli provider-verify --probe-mode real` | 发起 provider 轻量在线探测 |
| `python -m app.cli provider-smoke <query> --probe-mode real` | 运行 provider smoke，总结下一步动作 |
| `python -m app.cli collect-tracked` | 手动刷新全部追踪词 |

### 3.3 网页入口

当前默认网页由 FastAPI 直接提供：

- 路径：`/`
- 追踪页路径：`/tracked`
- 静态资源路径：`/assets/*`
- 核心交互：输入查询、选择时间范围、切换内容来源、发起搜索、查看回填状态、切换 Track/Untrack、查看最近搜索、查看追踪列表、查看 scheduler 状态、查看 provider 预检、触发 provider 在线探测、运行 provider smoke 总览、手动触发采集、查看最近采集日志

## 4. 启动流程

### 4.1 后端启动

后端启动时会执行：

1. 读取环境变量配置
2. 初始化 FastAPI 应用
3. 在 lifespan 阶段调用 `init_db()`
4. 使用 SQLAlchemy `Base.metadata.create_all()` 自动建表

当前没有独立迁移系统，数据库表由代码模型直接创建。

### 4.2 网页启动

浏览器打开 `/` 后加载静态页面，页面初始状态取决于 URL query：

- `q`
- `period`

如果 URL 里没有 `q`，页面只展示搜索框和空状态说明。

## 5. 配置流程

### 5.1 Provider 模式

后端通过 `PROVIDER_MODE` 控制数据来源策略：

- `mock`
  使用确定性的假数据，默认模式，适合离线开发和测试
- `real`
  使用真实 GitHub 和 NewsNow
- `auto`
  先尝试真实 provider，失败后回落到 mock

### 5.2 真实 provider 依赖的关键配置

- `GITHUB_TOKEN`
- `GITHUB_API_BASE_URL`
- `GITHUB_HISTORY_MAX_PAGES`
- `NEWSNOW_BASE_URL`
- `NEWSNOW_SOURCE_IDS`
- `REQUEST_TIMEOUT_SECONDS`
- `HTTP_PROXY`

### 5.3 调度器配置

自动采集由内置 scheduler 驱动，关键配置如下：

- `SCHEDULER_ENABLED`
- `SCHEDULER_INTERVAL_SECONDS`
- `SCHEDULER_INITIAL_DELAY_SECONDS`
- `SCHEDULER_PERIOD`
- `SCHEDULER_RUN_BACKFILL_NOW`

## 6. 搜索主流程

搜索是当前系统的主路径，API、CLI 和前端最终都会走到同一组服务函数。

### 6.1 输入分类

搜索输入先经过 `parse_search_query()` 规范化，分成两类：

- `github_repo`
  - GitHub URL
  - `owner/repo`
- `keyword`
  - 其他普通文本

规范化规则：

- 去掉首尾空格
- 折叠连续空白
- GitHub URL 转成小写 `owner/repo`
- 普通关键词转成小写 `normalized_query`

### 6.2 搜索入口调用链

`GET /api/search` 的实际处理顺序如下：

```text
request -> search_keyword()
        -> parse_period()
        -> parse_content_source()
        -> parse_search_query()
        -> get_or_create_keyword()
        -> _maybe_schedule_backfill()
        -> 读取 trend_points / content_items
        -> 拼装 snapshot / trend / availability / backfill_job
        -> 返回 SearchResponsePayload
```

### 6.3 关键词创建或复用

`get_or_create_keyword()` 的行为：

- 如果库里已有相同 `normalized_query + kind`
  - 更新 `raw_query`
  - 更新 `updated_at`
  - 复用原 keyword
- 如果库里没有
  - 新建 `keywords` 记录

### 6.4 是否触发回填

`_maybe_schedule_backfill()` 会判断是否需要创建 `backfill_job`：

- GitHub repository 查询且还没有 `github/star_delta` 历史数据
  - 创建 `github/history` 任务
- GitHub repository 查询且 GitHub 内容流为空或已过刷新窗口
  - 创建 `github/content` 任务
- NewsNow 快照不存在，或最近快照超过 30 分钟
  - 创建 `newsnow/snapshot` 任务

如果已有 `pending` 或 `running` 的任务，会直接复用。

如果最近一次 job 已经是 `failed` 或 `partial`：

- 普通搜索会直接返回这次失败结果，保留给前端展示
- 显式 refresh / collect 路径才会新建 job 重试

### 6.5 搜索返回策略

搜索接口不会等待所有后台数据完全准备好才返回。

它的返回策略是：

- 先返回当前已有数据
- 如果新建了 backfill job，把 job 状态和 task 状态一起返回
- 前端或调用方可以再轮询 `/backfill-status`
- 失败态不会在下一次普通搜索里立刻被新的 `pending` job 覆盖

这意味着第一次搜索某些词时，首包可能只有部分数据。

## 7. Backfill 流程

### 7.1 任务结构

当前 backfill 使用两层模型：

- `backfill_jobs`
  任务总状态
- `backfill_job_tasks`
  每个 source + task_type 的子任务状态

当前实际会出现的任务类型有三个：

- `github / history`
- `github / content`
- `newsnow / snapshot`

### 7.2 执行流程

`run_backfill_job(job_id)` 的执行顺序：

1. 打开新的数据库 session
2. 读取 job 和 keyword
3. 把 job 置为 `running`
4. 逐个执行 task
5. 成功或失败都写入 `collect_runs`
6. 计算 job 最终状态

### 7.3 GitHub history 流程

GitHub history 子任务的执行路径：

```text
job task -> provider.fetch_github_history(target_ref)
         -> 生成或抓取每日 star_delta 点位
         -> upsert 到 trend_points
         -> task 标记 success/failed/skipped
         -> collect_runs 记录一次 backfill
```

#### mock 模式

- 使用确定性的 45 天 star_delta 数据
- 数据随 repository 名字稳定变化

#### real 模式

- 先请求 repo 基本信息
- 再请求 stargazers 列表
- 按日期聚合成每日新增
- 受 `GITHUB_HISTORY_MAX_PAGES` 限制，超出时会标记 `truncated`

### 7.4 NewsNow snapshot 流程

NewsNow snapshot 子任务的执行路径：

```text
job task -> provider.fetch_newsnow_snapshot(query)
         -> 生成或抓取命中条目
         -> 写入 trend_points:
              - hot_hit_count
              - platform_count
         -> 写入 content_items
         -> task 标记 success/failed
         -> collect_runs 记录一次 backfill
```

#### mock 模式

- 生成固定数量的平台命中和内容条目
- 内容包括 `weibo`、`zhihu`、`bilibili`、`juejin`、`36kr`、`github`

#### real 模式

- 遍历 `NEWSNOW_SOURCE_IDS`
- 优先调用 `/api/s?id={source_id}`，旧版实例兼容回退到 `/api/s/{source_id}`
- 仅保留标题或名称里包含查询词的条目
- 聚合出命中条数和命中平台数

### 7.5 GitHub content 流程

GitHub content 子任务的执行路径：

```text
job task -> provider.fetch_github_content(target_ref)
         -> 拉取 release / issue / pull 标题与链接
         -> upsert 到 content_items
         -> task 标记 success/failed/skipped
         -> collect_runs 记录一次 backfill
```

#### mock 模式

- 生成确定性的 release / issue / pull 合成内容
- 用于离线验证 GitHub 内容流与筛选逻辑

#### real 模式

- 读取 GitHub Releases API
- 读取 GitHub Issues API，并把带 `pull_request` 标记的条目标记成 pull
- 按发布时间倒序合并后写入 `content_items`

### 7.6 Job 最终状态

job 最终状态由 task 状态推导：

- 全部成功：`success`
- 部分成功：`partial`
- 全部失败：`failed`

## 8. 搜索结果组装流程

回填调度完成后，搜索服务会从数据库重新读数据，并构造最终响应。

### 8.1 趋势图数据

趋势数据来自 `trend_points`：

- 先按 period 过滤
- 再按 `source + metric + source_type` 分组
- `platform_count` 不进入折线 series
- 对普通关键词，`newsnow/hot_hit_count` 会在返回前转换成本地累计曲线
- 输出 `trend.period` 和 `trend.series`

### 8.2 快照数据

快照来自各 metric 最近一条记录：

- `github/star_delta` -> `github_star_today`
- `newsnow/platform_count` -> `newsnow_platform_count`
- `newsnow/hot_hit_count` -> `newsnow_item_count`
- 最晚一条采集时间 -> `updated_at`

### 8.3 内容列表

内容列表来自 `content_items`：

- 可通过 `content_source=all|newsnow|github` 过滤
- 先按 `published_at desc, fetched_at desc`
- 最多取 20 条
- 再按 period 做时间过滤

当前来源边界：

- `real` provider 会写入 NewsNow 快照内容和 GitHub release / issue / pull 内容
- `mock` provider 会生成 NewsNow 与 GitHub 两类合成内容项

### 8.4 availability 字段

当前 availability 只关心两个维度：

- `github_history`
- `newsnow_snapshot`

它的值来自：

- 已有数据时默认 `ready`
- 有 job 时用 task 状态覆盖
- 对普通关键词，`github_history` 会被标记成 `not_applicable`

## 9. 网页流程

当前网页由 `backend/app/web/index.html + app.js + styles.css` 组成。

### 9.1 初次进入页面

页面读取 pathname 和 URL 参数：

- `/` 或 `/tracked`
- `q`
- `period`
- `content_source`

如果有 `q`，立即请求后端搜索接口。

### 9.2 用户提交搜索

提交表单时：

1. 阻止默认提交
2. 把 `q`、`period` 和可选的 `content_source` 写回 URL
3. 直接调用 `loadSearch()`

### 9.3 最近搜索与追踪列表

最近搜索：

1. 页面启动时从浏览器 `localStorage` 读取最近 10 条
2. 每次搜索成功后，把当前 query 写回本地缓存
3. 点击某条最近搜索，会恢复 query、period、content_source 并再次搜索

追踪列表：

1. 页面启动时调用 `GET /api/keywords?tracked_only=true`
2. `/tracked` 与 `/` 共用同一套静态页面和追踪列表数据
3. 点击追踪词会切回搜索页并立即重新搜索
4. 点击 Untrack 会调用 `DELETE /api/keywords/{id}/track`

追踪页运维区：

1. 页面启动时调用 `GET /api/collect/status`
2. 页面启动时调用 `GET /api/provider-status`
3. 页面启动时调用 `GET /api/collect/logs?limit=12`
4. 点击 Refresh 会同时刷新追踪词列表、scheduler 状态、provider 预检和最近采集日志
5. 点击 Verify real 会调用 `POST /api/provider-verify`
6. 在 `Provider preflight` 表单里填写 query / period / force_search 后，点击 Run smoke 会调用 `POST /api/provider-smoke`

### 9.4 前端搜索完成后的渲染

前端当前渲染这些模块：

- 状态胶囊
  - 查询词
  - kind
  - tracked 状态
  - backfill job 状态
  - task 状态
- 趋势卡片
  - 图例可单独显隐每条 series
  - 普通关键词会显示累计语义提示
  - 每个 series 一张卡
  - 使用 `Sparkline` 渲染折线
- 内容流
- 今日快照
- availability 面板
- 追踪列表面板
  - 当前追踪词
  - 最近更新时间
  - 直接跳转搜索
  - 直接取消追踪
- 追踪页运维面板
  - scheduler 状态快照
  - provider 本地预检
  - provider 在线探测结果
  - provider smoke summary / search status / next steps
  - 手动触发 tracked collect
  - 指定 query 的一次性 collect
  - 最近采集日志

### 9.5 回填状态轮询

如果返回的 `backfill_job.status` 是：

- `pending`
- `running`

前端会每 1.2 秒轮询一次 `/api/keywords/{id}/backfill-status`。

轮询过程：

1. 更新 `availability`
2. 更新 `backfill_job.tasks`
3. 如果 job 进入 `success/partial/failed`
   - 再请求一次完整搜索结果
   - 用最新结果覆盖页面

### 9.6 Track/Untrack 流程

点击 Track 按钮时：

1. 调用 `POST /api/keywords/{id}/track`
2. 成功后更新前端本地 `is_tracked`
3. 再刷新追踪列表面板

点击 Untrack 按钮时：

1. 调用 `DELETE /api/keywords/{id}/track`
2. 成功后更新前端本地 `is_tracked`
3. 再刷新追踪列表面板

### 9.7 追踪页运维流程

手动刷新运维数据时：

1. 调用 `GET /api/keywords?tracked_only=true`
2. 调用 `GET /api/collect/status`
3. 调用 `GET /api/provider-status`
4. 调用 `GET /api/collect/logs?limit=12`

触发 provider 在线探测时：

1. 调用 `POST /api/provider-verify`
2. 请求体为：
   - `probe_mode=real`
3. 后端会对 GitHub `rate_limit` 和 NewsNow 首个 source id 发起轻量请求
4. 页面展示每个数据源的 success / failed / skipped 和返回消息

运行 provider smoke 时：

1. 调用 `POST /api/provider-smoke`
2. 请求体为：
   - `query=<provider smoke 表单输入，默认为 openai/openai-python>`
   - `period=<provider smoke 表单所选周期>`
   - `probe_mode=real`
   - `force_search=<provider smoke 表单勾选状态>`
3. 后端会顺序执行：
   - provider 本地预检
   - provider 在线探测
   - 必要时执行一次同步搜索回填
4. 页面会同时展示：
   - summary
   - search.status / message
   - search.availability
   - next_steps

触发 tracked collect 时：

1. 调用 `POST /api/collect/trigger`
2. 请求体为：
   - `query=null`
   - `tracked_only=true`
   - `period=<所选周期>`
   - `run_backfill_now=<勾选状态>`
3. 成功后刷新追踪列表、scheduler 状态和采集日志

触发 one-off query collect 时：

1. 调用 `POST /api/collect/trigger`
2. 请求体为：
   - `query=<输入内容>`
   - `tracked_only=false`
   - `period=<所选周期>`
   - `run_backfill_now=<勾选状态>`
3. 成功后展示 `triggered_count` 和逐条结果状态

## 10. CLI 流程

CLI 是当前最完整的“无需前端即可操作系统”的入口。

### 10.1 `health`

直接调用 `health()`，输出 JSON。

### 10.2 `search`

调用 `refresh_keyword()`：

1. 先走一次 `search_keyword()`
2. 如果返回了 pending/running 的 backfill job，且没有传 `--no-backfill`
   - 立即在当前进程里同步执行 `run_backfill_job()`
3. 再次读取并输出最终搜索结果

这意味着 CLI 搜索默认比 HTTP 搜索“更完整”，因为它会同步等回填结束。

### 10.3 `track`

调用 `ensure_tracked()`：

1. 先确保关键词存在
2. 再把 `is_tracked` 设为 `true`

### 10.4 `collect-tracked`

调用 `collect_tracked_keywords()`：

1. 取出所有 `is_tracked=true` 的关键词
2. 对每个词调用 `refresh_keyword()`
3. 同步执行回填并返回结果列表

## 11. 关键词与采集管理流程

### 11.1 列出关键词

`GET /api/keywords`：

- 默认返回全部关键词
- 传 `tracked_only=true` 时只返回追踪词

### 11.2 创建关键词

`POST /api/keywords` 支持：

- `query`
- `track`
- `period`
- `run_backfill_now`

实际行为：

1. 先执行一次 `refresh_keyword()`
2. 如果 `track=true`
   - 再调用 `ensure_tracked()`
3. 返回 `SearchResponsePayload`

### 11.3 手动触发采集

`POST /api/collect/trigger` 有两种路径：

- 传 `query`
  - 只刷新这个词
- 不传 `query`
  - `tracked_only=true` 时刷新全部追踪词
  - `tracked_only=false` 时刷新全部关键词

返回：

- `triggered_count`
- 每个触发项的 query、keyword_id、status、tracked

### 11.4 采集日志

`GET /api/collect/logs`：

- 默认最多返回 50 条
- 数据来自 `collect_runs`

### 11.5 自动采集调度器

当前后端已经内置自动采集调度器：

1. 应用启动时读取 scheduler 配置
2. 如果 `SCHEDULER_ENABLED=true`
   - 在 lifespan 启动后台线程
3. 调度器按固定间隔执行一次 `trigger_collection(query=None, tracked_only=True, ...)`
4. 应用退出时停止调度器线程

当前可以通过两种方式查看它的状态：

- `GET /api/collect/status`
- `python -m app.cli scheduler-status`

## 12. 数据落库流程

当前 SQLite 表的职责如下：

| 表 | 作用 |
|---|---|
| `keywords` | 关键词主表 |
| `trend_points` | 趋势点位 |
| `content_items` | 内容条目 |
| `backfill_jobs` | 回填任务主表 |
| `backfill_job_tasks` | 回填任务子表 |
| `collect_runs` | 采集与回填执行日志 |

### 12.1 Search 时可能发生的写入

首次搜索时可能会写：

- `keywords`
- `backfill_jobs`
- `backfill_job_tasks`

### 12.2 Backfill 时可能发生的写入

回填执行时可能会写：

- `trend_points`
- `content_items`
- `collect_runs`
- `backfill_job_tasks` 状态
- `backfill_jobs` 状态

### 12.3 Track 操作时会写

- `keywords.is_tracked`
- `keywords.updated_at`

## 13. 当前测试覆盖

当前后端已经有基础回归测试，覆盖：

- 健康检查
- GitHub URL 规范化
- repository 搜索 + 回填
- Track/Untrack
- collector 路径
- management 列表与采集日志

这些测试都在 `backend/tests/test_services.py`。

## 14. 当前实现边界

以下能力已经在文档或 PRD 中出现，但当前代码还没有完整实现：

- 多页面前端管理后台
  当前前端只有搜索页
- 综合指数
- 权重配置
- 热词发现
- 事件标注
- 数据导出
- 推送通知
- 完整真实 provider 联调验证
  `real` 模式代码已存在，但当前环境下未做在线验证

## 15. 当前推荐使用方式

如果目标是稳定体验当前实现，推荐顺序如下：

1. 本地开发和测试使用 `PROVIDER_MODE=mock`
2. 用 CLI 验证主流程
3. 用 API 验证路由和状态流转
4. 最后再接前端页面

如果目标是开始接真实外部数据：

1. 把 `PROVIDER_MODE` 切到 `auto`
2. 配好 GitHub token、NewsNow base URL 和代理
3. 先从 CLI 或 API 验证真实 provider
4. 通过后再做前端联调
