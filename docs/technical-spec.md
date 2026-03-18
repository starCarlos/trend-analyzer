# TrendScope MVP Technical Spec

> 版本：v1.0
> 日期：2026-03-17
> 状态：实现基线

## 1. 目标

为 MVP 提供唯一的技术执行口径，重点解决原始草稿中的三个问题：

- 产品范围和实现范围混写
- 表结构、接口、流程定义不一致
- 冷启动异步回填缺少状态模型

## 2. 设计原则

- 先跑通最短闭环，不为未来的 20 个数据源提前设计复杂抽象
- 接受数据源能力不对齐，不强行造一个伪统一指标
- 所有异步回填都必须可观测、可重试、可部分成功
- 数据库中的主事实必须稳定，不依赖运行时重新归一化

## 3. MVP 数据源边界

### 3.1 必做数据源

| 数据源 | 用途 | 支持对象 | 历史能力 |
|---|---|---|---|
| GitHub REST / star history | 仓库 star 日增趋势 | GitHub 项目 | 完整历史 |
| NewsNow API | 热榜快照与条目内容 | 普通关键词、GitHub 项目 | 仅当前快照 |

### 3.2 明确后置

- Google Trends
- Reddit
- YouTube
- Product Hunt
- npm / PyPI / Stack Overflow
- 综合指数和权重系统

## 4. 输入分类规则

搜索输入在进入业务流程前必须规范化。

### 4.1 分类

- `github_repo`
  - GitHub URL
  - `owner/repo`
- `keyword`
  - 其他所有普通文本

### 4.2 规范化

- 去前后空格
- GitHub URL 转成小写 `owner/repo`
- 连续空白折叠为一个空格
- 保留原始输入，另存 `normalized_query`

### 4.3 不做的事

MVP 不自动把普通关键词猜成 GitHub 仓库，也不做模糊映射。

## 5. 系统架构

```text
FastAPI
    |- Web UI
    |- Search Service
    |- Backfill Job Service
    |- Collector Service
    |
    +--> SQLite
    |
    +--> GitHub API
    |
    +--> NewsNow API
```

说明：

- 搜索请求只负责返回当前可用数据和任务状态
- 回填任务由后端异步执行
- 定时采集只处理已加入追踪的关键词

## 6. 数据模型

以下表结构替代原稿中重复且不一致的版本。

### 6.1 `keywords`

```sql
CREATE TABLE keywords (
    id               INTEGER PRIMARY KEY,
    raw_query        TEXT NOT NULL,
    normalized_query TEXT NOT NULL,
    kind             TEXT NOT NULL,      -- 'github_repo' | 'keyword'
    target_ref       TEXT,               -- github_repo 时存 owner/repo
    is_tracked       BOOLEAN DEFAULT FALSE,
    first_seen_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(normalized_query, kind)
);
```

### 6.2 `trend_points`

用统一时间桶替代 `date + hour` 组合，避免可空唯一键带来的重复数据问题。

```sql
CREATE TABLE trend_points (
    id                 INTEGER PRIMARY KEY,
    keyword_id         INTEGER NOT NULL REFERENCES keywords(id),
    source             TEXT NOT NULL,    -- 'github' | 'newsnow'
    metric             TEXT NOT NULL,    -- 'star_delta' | 'hot_hit_count'
    source_type        TEXT NOT NULL,    -- 'backfill' | 'snapshot' | 'scheduled'
    bucket_granularity TEXT NOT NULL,    -- 'hour' | 'day'
    bucket_start       DATETIME NOT NULL,
    value              REAL NOT NULL,
    raw_json           TEXT,
    collected_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(keyword_id, source, metric, source_type, bucket_granularity, bucket_start)
);
```

### 6.3 `content_items`

```sql
CREATE TABLE content_items (
    id               INTEGER PRIMARY KEY,
    keyword_id       INTEGER NOT NULL REFERENCES keywords(id),
    source           TEXT NOT NULL,      -- 'newsnow' | 'github'
    source_type      TEXT NOT NULL,      -- 'backfill' | 'snapshot' | 'scheduled'
    external_key     TEXT NOT NULL,      -- URL 或外部唯一 ID
    title            TEXT NOT NULL,
    url              TEXT,
    summary          TEXT,
    author           TEXT,
    published_at     DATETIME,
    meta_json        TEXT,
    fetched_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_key)
);
```

### 6.4 `backfill_jobs`

```sql
CREATE TABLE backfill_jobs (
    id               INTEGER PRIMARY KEY,
    keyword_id       INTEGER NOT NULL REFERENCES keywords(id),
    status           TEXT NOT NULL,      -- 'pending' | 'running' | 'success' | 'partial' | 'failed'
    requested_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at       DATETIME,
    finished_at      DATETIME,
    error_message    TEXT
);
```

### 6.5 `backfill_job_tasks`

按来源记录状态，支撑前端轮询。

```sql
CREATE TABLE backfill_job_tasks (
    id               INTEGER PRIMARY KEY,
    job_id           INTEGER NOT NULL REFERENCES backfill_jobs(id),
    source           TEXT NOT NULL,      -- 'github' | 'newsnow'
    task_type        TEXT NOT NULL,      -- 'history' | 'content' | 'snapshot'
    status           TEXT NOT NULL,      -- 'pending' | 'running' | 'success' | 'failed' | 'skipped'
    message          TEXT,
    started_at       DATETIME,
    finished_at      DATETIME,
    UNIQUE(job_id, source, task_type)
);
```

### 6.6 `collect_runs`

```sql
CREATE TABLE collect_runs (
    id               INTEGER PRIMARY KEY,
    keyword_id       INTEGER REFERENCES keywords(id),
    source           TEXT NOT NULL,
    run_type         TEXT NOT NULL,      -- 'scheduled' | 'manual' | 'backfill'
    status           TEXT NOT NULL,      -- 'success' | 'failed' | 'partial'
    duration_ms      INTEGER,
    message          TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 7. 冷启动状态机

### 7.1 触发条件

满足任一条件时创建回填任务：

- 关键词首次搜索
- GitHub 项目缺少历史 star 数据
- GitHub 项目缺少内容流，或 GitHub 内容超过刷新窗口
- NewsNow 快照超过 `30` 分钟未刷新

### 7.2 请求流程

```text
GET /api/search?q=owner/repo&content_source=github
    |
    |- Step 1: 规范化并查 keywords
    |- Step 2: 读取本地 trend_points / content_items
    |- Step 3: 如需补数则创建或复用 backfill_job
    |- Step 4: 立即返回当前数据 + job 状态
    |
background workers
    |- GitHub history task
    |- GitHub content task
    |- NewsNow snapshot task
    |- 任务结束后写 trend_points / content_items / tasks
```

补充规则：

- 普通 `GET /api/search` 不会在最近一次 job 已 `failed/partial` 时立刻重建新 job
- 显式 refresh / collect 才会把失败任务重新排队

### 7.3 状态规则

- `pending`
  任务已创建，尚未开始
- `running`
  至少一个子任务在执行
- `success`
  所有必做子任务成功
- `partial`
  至少一个子任务成功，至少一个子任务失败
- `failed`
  所有必做子任务失败

### 7.4 前端渲染规则

- 有缓存数据先渲染缓存
- `backfill_job.status in ('pending', 'running')` 时显示“数据加载中”
- 某来源任务 `failed` 时，该来源显示灰态说明，不阻塞其他来源
- 普通搜索要保留最近一次 `failed/partial` 结果，避免错误信息被新的 `pending` 状态立刻冲掉
- 前端支持图例显隐
- 普通关键词的 `newsnow/hot_hit_count` 按当前展示窗口渲染为累计曲线

## 8. API 约定

### 8.1 `GET /api/search`

用途：发起搜索并返回当前可用结果。

请求：

```text
GET /api/search?q=anthropic/claude-code&period=30d
```

响应：

```json
{
  "keyword": {
    "id": 12,
    "raw_query": "anthropic/claude-code",
    "normalized_query": "anthropic/claude-code",
    "kind": "github_repo",
    "is_tracked": false
  },
  "availability": {
    "github_history": "ready",
    "newsnow_snapshot": "running"
  },
  "snapshot": {
    "github_star_today": 128,
    "newsnow_platform_count": 2,
    "newsnow_item_count": 5,
    "updated_at": "2026-03-17T10:12:00Z"
  },
  "trend": {
    "period": { "start": "2026-02-17", "end": "2026-03-17" },
    "series": [
      {
        "source": "github",
        "metric": "star_delta",
        "source_type": "backfill",
        "points": [
          { "bucket_start": "2026-03-15T00:00:00Z", "value": 81 }
        ]
      }
    ]
  },
  "content_items": [],
  "backfill_job": {
    "id": 33,
    "status": "running"
  }
}
```

### 8.2 `GET /api/keywords/{id}/backfill-status`

用途：前端轮询异步回填状态。

响应：

```json
{
  "job_id": 33,
  "status": "partial",
  "tasks": [
    { "source": "github", "task_type": "history", "status": "success" },
    { "source": "newsnow", "task_type": "snapshot", "status": "failed", "message": "429 rate limited" }
  ]
}
```

### 8.3 `POST /api/keywords/{id}/track`

用途：加入追踪。

行为：

- `is_tracked=false -> true`
- 创建后续定时采集对象

### 8.4 `DELETE /api/keywords/{id}/track`

用途：取消追踪。

行为：

- 仅停止后续采集
- 不删除历史数据

## 9. 采集策略

### 9.1 即时采集

- 搜索时触发
- GitHub：仅 `github_repo` 类型执行历史回填
- GitHub：`github_repo` 类型同时补 GitHub 内容流
- NewsNow：两类关键词都执行快照采集

### 9.2 定时采集

- 仅针对 `is_tracked=true` 的关键词
- GitHub：每 6 小时刷新一次当日累计，再按天落库
- NewsNow：每 30 分钟抓一次快照，按天聚合 `hot_hit_count`

## 10. 非功能要求

### 10.1 性能

- `GET /api/search` 首包 P95 小于 `2s`
- 单个回填任务总时长 P95 小于 `10s`

### 10.2 可靠性

- 外部 API 请求默认超时 `8s`
- 单次请求最多重试 `2` 次，指数退避
- 所有失败必须写 `collect_runs`

### 10.3 可观测性

至少记录以下字段：

- request_id
- keyword_id
- source
- run_type
- status
- duration_ms

### 10.4 配置项

- `GITHUB_TOKEN`
- `NEWSNOW_BASE_URL`
- `HTTP_PROXY`
- `DATABASE_URL`

## 11. 明确暂不实现

- 用户体系和多租户
- 权重配置表
- 综合指数持久化
- 多数据源统一归一化
- 通知系统

## 12. Phase 2 预留

如果后续重启“综合指数”方案，必须单独增加一份设计，不允许直接复用原稿中的运行时 `min-max` 公式。
原因是该公式会重写历史解释，不适合作为稳定指标。
