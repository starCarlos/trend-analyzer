# TrendScope — 跨平台热度分析工具 PRD

> 版本：v0.7 · 日期：2026-03-17 · 状态：草稿
> 更新：F8 新增 8.3 历史数据回溯（各数据源回溯能力对比表、并发多通道查询流程、流式渲染策略、数据桶聚合逻辑、source_type 字段规范），8.4 搜索冷启动重写为两组并发请求，新增 `/backfill_status` 接口

---

## 一、产品背景

### 1.1 问题陈述

现有热度工具各有局限：

- **微信指数**：仅覆盖微信生态，无公开 API，数据无法导出
- **百度指数**：仅覆盖百度搜索，需付费获取完整数据
- **Google Trends**：国内访问受限，数据归一化（0-100）非绝对值
- **TrendRadar 类工具**：推送今日热点列表，但**不存储历史数据，无法画趋势折线图**

**核心空白**：没有一个工具能把微博、头条、B站、GitHub、Google Trends 等多个来源的关键词热度，**聚合到同一张随时间变化的折线图上**进行横向对比。

### 1.2 产品定位

一句话：**微信指数体验 × 多平台数据源 × 可自部署**

目标用户：
- 关注 AI/开源项目热度的开发者
- 做舆情追踪的内容创作者、产品经理
- 需要竞品热度对比的市场研究者

---

## 二、核心功能需求

### 2.1 功能全景

```
TrendScope
├── 关键词搜索        搜索即查询，搜索即追踪（F8，新增）
├── 热词发现          自动从多平台提取高热词，一键加入追踪（F7，新增）
├── 关键词管理        输入、保存、分组管理追踪词（F3）
├── 数据采集层        定时从各平台拉取热度数据并存储（F2）
├── 折线图看板        综合/分平台/自定义权重三视图，数据源多选单选（F1）
├── 事件标注          在折线图上标记重要事件节点（F4）
├── 数据导出          CSV / JSON 导出（F5）
└── 推送通知          异常热度波动推送到飞书/Telegram（F6）
```

### 2.2 核心功能详述

#### F1 · 折线图看板（核心，优先级 P0）

##### 1.1 三种视图模式

折线图支持三种观察维度，通过顶部 Tab 切换：

```
[综合指数]  [分平台对比]  [自定义权重]
```

**模式一：综合指数**（默认视图）

将所有选中数据源按权重合并为一条"综合热度"曲线，适合快速判断趋势方向。Y 轴为综合热度分（0-100归一化）。

**模式二：分平台对比**

每个数据源独立一条线，在同一图上叠加展示。用户可以多选/单选数据源，观察各平台热度的差异和时间差。适合判断"先在哪个平台热起来"。

**模式三：自定义权重**

用户自己设置各平台的权重系数，系统实时重新计算综合曲线。适合有特定关注重点的用户（如只关心国内社交平台，GitHub 权重设为 0）。

---

##### 1.2 数据源多选 / 单选控件

位于图表下方的平台选择器：

```
数据源：
[✓ 综合] [✓ GitHub] [✓ 微博] [✓ 知乎] [ 头条] [✓ B站] [ Google] [ Reddit]
                                                         全选  反选  重置
```

交互规则：
- 默认全选，综合曲线 + 各分平台曲线同时展示
- 点击某平台 tag 切换勾选状态，图表实时更新（无需重新请求后端）
- 仅勾选一个平台时，自动切换为「单平台」视图，Y 轴显示该平台的原始数值（非归一化）
- 多个平台同时勾选且处于「分平台对比」模式时，各平台使用独立左/右 Y 轴（最多双轴）或归一化到统一轴（可在设置中切换）
- 「综合」曲线始终置顶，颜色固定为深色，不可与单平台线混淆

---

##### 1.3 权重配置面板

点击右上角「自定义权重」按钮，或切换到「自定义权重」Tab，展开权重面板：

```
┌──────────────────────────────────────────────┐
│  权重配置                          [重置默认] │
│                                              │
│  GitHub star     ████████░░  0.30  [−][+]   │
│  微博            ██████░░░░  0.20  [−][+]   │
│  知乎            ██████░░░░  0.20  [−][+]   │
│  B站             ████░░░░░░  0.15  [−][+]   │
│  头条            ████░░░░░░  0.15  [−][+]   │
│  Google Trends   ░░░░░░░░░░  0.00  [−][+]   │
│                                              │
│  权重总和：1.00 ✓           [应用并重算]    │
└──────────────────────────────────────────────┘
```

交互细节：
- 每个平台一行：平台名 + 进度条（直观显示比例）+ 数值输入 + `[−][+]` 微调按钮
- 拖动进度条可直接调整权重
- 权重总和实时显示，非 1.00 时标红提示，点击「应用并重算」才会归一化并重新绘图
- 也可点击「锁定其他」后调整单个平台权重，系统自动按比例分配剩余权重给其他平台
- 权重配置可命名保存（如「技术圈关注度」「大众舆情」），支持多套预设切换
- 预设配置存入 `user_weight_presets` 表，下次搜索同类词时可复用

---

##### 1.4 综合指数计算公式

```python
# 各平台原始值先做 min-max 归一化到 [0, 100]
normalized[platform] = (raw - min) / (max - min) * 100

# 按用户设定权重加权求和
composite_score = sum(
    normalized[platform] * weight[platform]
    for platform in selected_platforms
) / sum(weights)  # 权重归一，允许权重之和不为1

# 默认权重（按信号类型分组）
DEFAULT_WEIGHTS = {
    # 开发者采用度（合计 0.35）
    "github_star":    0.20,
    "npm_downloads":  0.08,
    "pypi_downloads": 0.04,
    "docker_pulls":   0.03,
    # 社区讨论度（合计 0.25）
    "hacker_news":    0.10,
    "zhihu":          0.08,
    "v2ex":           0.04,
    "stackoverflow":  0.03,
    # 大众热搜（合计 0.20）
    "weibo":          0.12,
    "toutiao":        0.08,
    # 媒体覆盖度（合计 0.10）
    "36kr":           0.04,
    "huxiu":          0.03,
    "sspai":          0.03,
    # 内容扩散度（合计 0.10）
    "bilibili":       0.06,
    "devto":          0.04,
    # 默认关闭，需手动启用
    "google_trends":  0.00,
    "reddit":         0.00,
    "youtube":        0.00,
    "product_hunt":   0.00,
}
```

归一化说明：
- min/max 取该关键词该平台的**历史区间内最大最小值**，而非当日数据
- 新词冷启动时 min=0，max 用同类词的历史中位数估算，待积累后自动修正

---

##### 1.5 其他图表交互

- 时间维度切换：近 7 天 / 近 30 天 / 近 90 天 / 全部（右上角 Tab）
- 悬停 Tooltip：显示该日期各平台原始值 + 综合指数，方便对比
- 折线样式：平滑曲线 / 阶梯（右键菜单切换）
- Y 轴：综合模式下单轴 + 归一化；分平台模式下支持双轴（左轴社交平台，右轴 GitHub）
- 对数坐标：右上角「log」开关，适合量级差异极大时（如 GitHub star 几十万 vs 热榜出现 3 次）
- 区间缩放：鼠标滚轮或拖选放大局部时间段
- 导出当前视图：PNG / SVG / CSV（保留当前所选数据源和权重配置）

---

##### 1.6 新增数据库表

```sql
-- 用户权重预设表
CREATE TABLE user_weight_presets (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,           -- 预设名称，如"技术圈关注度"
    weights     TEXT NOT NULL,           -- JSON，如 {"github_star":0.5,"weibo":0.3,...}
    is_default  BOOLEAN DEFAULT FALSE,
    created_at  DATETIME DEFAULT NOW()
);
```

#### F2 · 数据来源

数据源按接入成本和优先级分三批，系统设计为插件式适配器架构，新增数据源只需实现统一接口。

---

##### 2.1 核心底座（第一批，MVP 必须有）

**NewsNow** 是最重要的底座，直接替代原方案中的 TrendRadar。

| 项目 | 说明 |
|---|---|
| 项目地址 | https://github.com/ourongxing/newsnow |
| 线上实例 | https://newsnow.busiyi.world |
| 数据源数量 | 40+ 个平台，持续增加 |
| 接入方式 | 官方 MCP Server（`newsnow-mcp-server`）或直接调用 REST API；可自部署 Docker 实例 |
| 优势 | MIT 开源，18k+ star，有官方维护，结构化数据，支持自托管，是 TrendRadar 的上游数据来源 |

NewsNow 覆盖平台（部分）：
```
国内社交：  微博、知乎、B站、抖音、小红书、贴吧
国内科技：  掘金、少数派、36kr、虎嗅、澎湃、财联社、华尔街见闻
国内娱乐：  今日头条、百度热搜、凤凰网、爱奇艺、腾讯视频
国际平台：  Hacker News、Product Hunt、GitHub Trending
```

**GitHub API**（第一批）

| 采集内容 | 更新频率 | 技术方案 |
|---|---|---|
| 指定仓库 star/fork/watch 日增量 | 每日 | REST API，免费 Token 5000次/小时 |
| 关键词仓库搜索量（相关项目数） | 每日 | Search API |
| GitHub Trending 榜单 | 每日 | Trending 页面解析 |
| star 历史数据补全 | 一次性 | star-history API 或 GitHub Events API |

---

##### 2.2 开发者生态（第二批）

| 数据源 | 采集内容 | 接入方式 | 价值信号 |
|---|---|---|---|
| **npm** | 关键词包的周下载量趋势 | 免费，`api.npmjs.org/downloads` | JS/TS 生态实际使用量，比 star 更真实 |
| **PyPI** | Python 包日下载量 | 免费，`pypistats.org/api` | Python 生态使用量 |
| **Docker Hub** | 镜像 pull 次数 | 免费，Docker Hub API | 部署热度，反映生产环境采用率 |
| **Hacker News** | 关键词相关帖子数 + 评论热度分 | 免费，Algolia HN Search API | 硅谷技术圈风向标，响应快 |
| **Product Hunt** | 产品 upvote 数 + 日榜排名 | 免费 GraphQL API | 新产品发布热度，适合追踪新工具 |
| **Stack Overflow** | 关键词相关问题数量趋势 | 免费，Stack Exchange API | 开发者学习曲线，热度滞后但持久 |
| **Dev.to** | 关键词相关文章数 + 阅读量 | 免费 REST API | 开发者技术博客热度 |

---

##### 2.3 搜索引擎（第二批）

| 数据源 | 采集内容 | 接入方式 | 备注 |
|---|---|---|---|
| **Google Trends** | 搜索指数（0-100 归一化） | pytrends（国内需代理） | 全球搜索热度基准 |
| **Bing Web Search** | 关键词月搜索量估算 | Bing Search API（免费额度 1000次/月） | Google 国内替代方案 |
| **百度指数** | 国内搜索热度 | 无官方 API，爬虫有风险 | 国内最重要的搜索信号，暂列观察 |

---

##### 2.4 国际社交媒体（第二批）

| 数据源 | 采集内容 | 接入方式 | 备注 |
|---|---|---|---|
| **Reddit** | 关键词相关帖子数 + 热度分 | PRAW 库，免费注册 | 英文社区深度讨论 |
| **YouTube** | 关键词相关视频数 + 总观看量趋势 | YouTube Data API，免费额度 | 视频内容扩散信号 |
| **Twitter/X** | 关键词推文数 + 互动量 | 基础版 $100/月 | 成本较高，按需评估 |

---

##### 2.5 国内内容平台 RSS（第一批，低成本扩展）

以下平台 NewsNow 未完全覆盖，通过 RSS 补充：

| 平台 | RSS 地址 | 采集内容 |
|---|---|---|
| 掘金 | `juejin.cn/rss` | 相关文章数 + 热度 |
| 少数派 | `sspai.com/feed` | 相关文章 + 收藏量 |
| 36kr | `36kr.com/feed` | 科技媒体报道数量 |
| 虎嗅 | `huxiu.com/rss` | 商业科技报道量 |
| V2EX | `v2ex.com/index.xml` | 极客社区帖子数 |

---

##### 2.6 暂缓接入（高风险）

| 数据源 | 原因 |
|---|---|
| 微信指数 | 无官方 API，爬虫属灰色地带 |
| 微博指数 | 同上 |
| 小红书 | 无公开 API，且 NewsNow 已部分覆盖 |
| LinkedIn | 基本无开放 API |

---

##### 2.7 数据源分类总览

按信号类型分组，方便用户在权重配置面板中按组操作：

```
📦 开发者采用度     GitHub star/fork、npm 下载、PyPI 下载、Docker pull
🔍 搜索热度         Google Trends、Bing 搜索量、百度指数（暂缓）
💬 社区讨论度       Hacker News、Reddit、Stack Overflow、V2EX、Dev.to
📰 媒体覆盖度       36kr、虎嗅、少数派、NewsNow 新闻聚合
🎬 内容扩散度       B站、YouTube、抖音（via NewsNow）
🔥 大众热搜         微博、知乎、今日头条、百度热搜（via NewsNow）
🚀 产品热度         Product Hunt upvote、掘金热度
```

每个分组在权重配置面板中可整组调节，也可展开单独调节各平台权重。

---

##### 2.8 爬虫与数据采集实现方案

针对国内热榜数据（NewsNow 覆盖的 40+ 平台）有三种接入方式，按开发阶段递进使用。

---

**方案 A：复用 TrendRadar 的 `main.py`（MVP 首选，最快落地）**

TrendRadar 本质上是：调用 NewsNow API → 关键词过滤 → 推送。我们只需在它的输出环节前插入一步「写入数据库」，就能把实时热点列表变成时序数据。

```
TrendRadar main.py（原有逻辑）
    ↓ 每小时执行
调用 newsnow.busiyi.world API
    ↓ 拿到各平台热榜
关键词匹配过滤
    ↓ ← 在这里插入我们的逻辑
写入 trend_data 表 + news_items 表    ← 新增
    ↓
（原有推送逻辑可选保留）
```

改造工作量：约 50-100 行 Python，在原有 `main.py` 中加存储钩子。

优点：无需自建爬虫，开发最快，数据结构已验证，部署简单（GitHub Actions 或 Docker）。

缺点：依赖 `newsnow.busiyi.world` 公网服务，稳定性取决于第三方，数据有 30 分钟缓存延迟。

参考代码位置：`https://github.com/joyce677/TrendRadar/blob/main/main.py`

---

**方案 B：调用 NewsNow REST API / MCP（中期过渡）**

NewsNow 提供两种接入接口，跳过 TrendRadar 这一层，数据更直接：

```python
# 方式一：REST API（无需认证）
GET https://newsnow.busiyi.world/api/s/{source_id}
# 返回指定平台的当前热榜列表
# source_id 示例：weibo-hot、zhihu-hot、bilibili-hot、hn-best

# 方式二：官方 MCP Server
# 在后端进程中启动 MCP 客户端
npx newsnow-mcp-server  # BASE_URL 指向自部署实例或公网实例
```

接入示例：
```python
import httpx

NEWSNOW_BASE = "https://newsnow.busiyi.world"
SOURCES = ["weibo-hot", "zhihu-hot", "bilibili-hot", "toutiao-hot",
           "hn-best", "github-trending", "juejin-hot"]

async def fetch_platform(source_id: str, keyword: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{NEWSNOW_BASE}/api/s/{source_id}")
        items = r.json().get("items", [])
        # 关键词匹配
        matched = [i for i in items if keyword.lower() in i["title"].lower()]
        return {"source": source_id, "matched": matched, "total": len(items)}
```

优点：接口结构比 TrendRadar 更干净，支持 MCP 协议（可与 Claude Code 等工具联动），可选自部署消除第三方依赖。

缺点：公网实例存在速率限制，source_id 列表需要维护，数据仍有缓存延迟（NewsNow 默认 30 分钟）。

参考：`https://github.com/ourongxing/newsnow-mcp-server`

---

**方案 C：自部署 NewsNow + 直接复用其爬虫代码（长期目标）**

NewsNow 的真正爬虫逻辑在 `server/sources/` 目录，每个平台一个 TypeScript 文件，直接对目标平台发请求并解析。自部署后数据实时、无延迟、无外部依赖。

```
自部署 NewsNow Docker 实例
    ↓
server/sources/weibo.ts      → 直接爬微博热榜
server/sources/zhihu.ts      → 直接爬知乎热榜
server/sources/bilibili.ts   → 直接爬B站热搜
... (40+ 平台)
    ↓
我们的 FastAPI 后端直接调本地 NewsNow API
    ↓ 无缓存延迟，实时数据
写入数据库
```

部署命令：
```bash
# 自部署 NewsNow（需配置 Cloudflare D1 或 SQLite）
git clone https://github.com/ourongxing/newsnow
cd newsnow
docker compose up -d
# 之后本地访问 http://localhost:3000/api/s/{source_id}
```

优点：数据最新（最快 2 分钟一次），完全自控，无第三方依赖，可以直接修改采集逻辑。

缺点：需要维护一个额外的 NewsNow 服务，初始配置成本略高（需要 D1 数据库或本地 SQLite 配置）。

参考：`https://github.com/ourongxing/newsnow/blob/main/Dockerfile`

---

**三方案对比总览**

| 维度 | 方案 A：复用 TrendRadar | 方案 B：调 NewsNow API | 方案 C：自部署 NewsNow |
|---|---|---|---|
| 开发工作量 | 最小（改 50 行） | 小（写适配器） | 中（部署 + 配置） |
| 数据实时性 | 30 分钟延迟 | 30 分钟延迟 | 最快 2 分钟 |
| 外部依赖 | TrendRadar + NewsNow | NewsNow 公网 | 无 |
| 稳定性 | 受两层依赖影响 | 受 NewsNow 公网影响 | 完全自控 |
| 平台覆盖 | TrendRadar 支持的 | NewsNow 全部 40+ | NewsNow 全部 40+ |
| 推荐阶段 | **MVP 阶段** | **阶段二过渡** | **阶段三长期** |

---

**其他数据源的独立适配器**

NewsNow 未覆盖的数据源（npm、PyPI、HackerNews、StackOverflow 等）需要单独实现 Python 适配器，每个适配器实现统一接口：

```python
class DataSourceAdapter:
    source_id: str           # 数据源唯一标识，如 "npm"
    update_interval: int     # 建议采集间隔（秒）

    async def fetch(self, keyword: str) -> AdapterResult:
        """
        返回标准结构：
        {
            "keyword": keyword,
            "source": self.source_id,
            "date": today,
            "value": float,          # 热度数值
            "raw": dict,             # 原始数据备份
            "items": list[NewsItem]  # 相关内容条目（可选）
        }
        """
        raise NotImplementedError
```

各平台适配器实现复杂度：

| 适配器 | API 文档 | 实现难度 | 备注 |
|---|---|---|---|
| npm | `api.npmjs.org/downloads/range/{period}/{package}` | 低 | 返回 JSON，结构清晰 |
| PyPI | `pypistats.org/api/packages/{pkg}/overall` | 低 | 同上 |
| Docker Hub | `hub.docker.com/v2/repositories/{image}` | 低 | 免费无需认证 |
| HackerNews | Algolia 搜索 API，`hn.algolia.com/api/v1/search` | 低 | 完全免费 |
| StackOverflow | `api.stackexchange.com/2.3/search` | 低 | 每日 10000 次免费 |
| ProductHunt | GraphQL，`api.producthunt.com/v2/api/graphql` | 中 | 需注册获取 token |
| Dev.to | `dev.to/api/articles?tag={keyword}` | 低 | 完全免费 |
| Google Trends | pytrends 库 | 中 | 国内需代理，有反爬 |
| Reddit | PRAW 库 | 低 | 需注册 app 获取 client_id |
| YouTube | `googleapis.com/youtube/v3/search` | 低 | 每日 10000 单位免费 |

- 添加/删除/分组管理追踪词
- 支持两种模式：
  - **词语模式**：追踪任意关键词（如"openclaw"、"人工智能"）
  - **项目模式**：直接输入 GitHub 仓库地址，自动追踪 star/fork 趋势
- 关键词有效性验证（至少在一个数据源中能查到数据）

#### F4 · 事件标注（P1）

- 在折线图的指定日期添加标注文字（如"3.2 openclaw 登顶 GitHub"）
- 标注以竖线 + 气泡形式显示在图表上
- 支持手动添加和批量导入（CSV）

#### F5 · 数据导出（P1）

- 导出当前图表数据为 CSV（日期、关键词、各平台数值）
- 导出图表为 PNG/SVG
- 提供 JSON API 接口供外部调用

#### F6 · 异常推送（P2）

- 设置热度阈值，当某关键词的单日涨幅超过阈值时触发推送
- 支持推送到飞书 Bot、Telegram Bot
- 推送内容包含：关键词、当前热度值、涨幅、简要折线图（文字版）

#### F7 · 热词自动发现（P1）

**核心问题**：用户不知道该追踪什么词时，系统主动发现并推荐。

**工作流程**：
```
每小时定时任务
    ↓
从 TrendRadar 各平台热榜提取所有词条标题
    ↓
分词 + 去停用词 + 提取实体词
    ↓
计算跨平台综合热度分
    ↓
写入 discovered_keywords 表
    ↓
前端「发现」页展示今日飙升词 Top20
用户点击感兴趣的词 → 一键加入追踪列表
```

**热度评分公式**：
```python
score = (
    出现平台数量  × 0.30   # 跨平台覆盖度，最大权重
  + 平均排名倒数  × 0.40   # 排名越靠前分越高（如榜单第1名得1.0，第50名得0.02）
  + 近24h出现次数 × 0.30   # 同一词在多个时段多次出现
) × 100
```

**页面交互**：
- 「发现」Tab，按评分降序展示卡片列表
- 每张卡片显示：词名、综合分、出现平台 Tag、24h 出现次数
- 「+ 追踪」按钮一键加入关键词管理
- 支持按平台筛选（只看微博热词 / 只看 B站热词）
- 每日榜、每周榜切换

**数据库新增表**：
```sql
CREATE TABLE discovered_keywords (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    score        REAL NOT NULL,          -- 综合热度分 0-100
    sources      TEXT NOT NULL,          -- 出现平台列表 JSON，如 ["weibo","zhihu","bilibili"]
    platform_cnt INTEGER DEFAULT 0,      -- 出现平台数
    appear_cnt   INTEGER DEFAULT 0,      -- 近24h出现次数
    avg_rank     REAL,                   -- 各平台平均排名
    first_seen   DATETIME,               -- 首次发现时间
    peak_score   REAL,                   -- 历史最高分
    peak_date    DATE,                   -- 达到峰值的日期
    is_tracked   BOOLEAN DEFAULT FALSE,  -- 用户是否已加入追踪
    date         DATE NOT NULL,          -- 统计日期（每天快照）
    UNIQUE(name, date)
);
```

#### F8 · 搜索结果页（P0）

搜索是产品的主入口。搜索一个关键词后，展示的不只是折线图，而是一个完整的**关键词情报页**，让用户一眼看清这个词现在有多热、热在哪里、热点内容是什么、和哪些词相关。

---

##### 8.1 页面整体布局

```
┌──────────────────────────────────────────────────────┐
│  🔍  openclaw         [7天 30天 90天 全部]  [+ 追踪]  │  ← 顶部搜索栏
└──────────────────────────────────────────────────────┘

┌─────────────────────────────┐  ┌───────────────────────┐
│  📈 热度趋势折线图           │  │  📊 今日数据快照       │
│                             │  │  综合热度指数  8,420   │
│  [多平台叠加折线图]          │  │  GitHub star  +1,203  │
│  GitHub ── 微博 ── 知乎     │  │  微博上榜     12次     │
│                             │  │  新闻提及     47篇     │
└─────────────────────────────┘  └───────────────────────┘

┌──────────────────────────────────────────────────────┐
│  📰 相关新闻 & 内容                          [更多 →] │
│  ┌──────────────────────────────┬──────────────────┐  │
│  │ 标题  来源  时间  摘要       │  平台筛选 Tab    │  │
│  │ ···                         │  全部/微博/知乎/ │  │
│  │ ···                         │  头条/B站/GitHub │  │
│  └──────────────────────────────┴──────────────────┘  │
└──────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌───────────────────────────┐
│  🏷️ 相关词           │  │  🗺️ 平台分布热力图         │
│  claude code  ████   │  │  微博   ████████  35%     │
│  AI Agent     ████   │  │  知乎   ██████    28%     │
│  GitHub star  ███    │  │  头条   ████      18%     │
│  开源         ███    │  │  B站    ███       14%     │
│  · · ·               │  │  其他             5%      │
└──────────────────────┘  └───────────────────────────┘
```

---

##### 8.2 模块详细说明

**模块 A：热度趋势折线图**

- 同 F1，多平台折线叠加，支持时间维度切换
- 额外功能：在图上自动标注本词的**峰值时间点**和**重大新闻节点**
- 右侧 Y 轴显示 GitHub star 数（量级不同，双轴），左侧 Y 轴显示社交平台热度
- 图例可点击显示/隐藏各平台线条

**模块 B：今日数据快照**（右上角数值卡片）

| 字段 | 数据来源 | 说明 |
|---|---|---|
| 综合热度指数 | 系统计算 | 各平台归一化后加权合并的综合分 |
| 较昨日涨跌 | trend_data 计算 | 环比变化，带箭头标色 |
| GitHub star | GitHub API | 今日新增 star 数 |
| 社交平台上榜 | TrendRadar | 今日在各平台热榜出现总次数 |
| 新闻提及量 | NewsAPI / RSS | 今日相关新闻文章数量 |
| 峰值平台 | 系统计算 | 今日热度最高的平台名 |

**模块 C：相关新闻 & 内容**（P0，核心）

这是用户"看完图想知道发生了什么"的直接答案。

数据来源优先级：
```
① TrendRadar 热榜条目（带链接、来源、时间）     → 实时，每小时更新
② NewsAPI / RSS 新闻聚合                         → 每日更新
③ GitHub Issues / PR 标题（仅 github_repo 类型） → 每日更新
```

展示样式：
```
┌────────────────────────────────────────────────────┐
│  [微博]  openclaw日活突破百万，开发者社区热议不断   │
│  📅 2026-03-16 14:32  🔥 热度排名 #3  👁 156万    │
│  「据报道，openclaw 单日活跃用户突破百万大关...」  │
│  [查看原文 →]                                      │
├────────────────────────────────────────────────────┤
│  [知乎]  OpenClaw 和 Claude Code 到底有什么区别？   │
│  📅 2026-03-15 09:15  👍 2,341 赞  💬 189 评论    │
│  「作为两款都很火的 AI 编程工具，从架构上看...」   │
│  [查看原文 →]                                      │
├────────────────────────────────────────────────────┤
│  [GitHub]  openclaw v2.1.0 Released               │
│  📅 2026-03-14  ⭐ +8,421 stars that day          │
│  「Major update: Added Skills marketplace...」     │
│  [查看原文 →]                                      │
└────────────────────────────────────────────────────┘
```

交互细节：
- 平台 Tab 筛选：全部 / 微博 / 知乎 / 头条 / B站 / GitHub / 新闻
- 时间筛选：今日 / 近3日 / 近7日
- 排序切换：按热度 / 按时间
- 每次拉取最多展示 20 条，「加载更多」分页
- 新闻条目和折线图联动：鼠标悬停某条新闻，折线图上对应日期高亮

**模块 D：相关词**

系统自动发现与当前关键词同期热度上涨的词，帮助用户发现关联话题。

计算逻辑：
```python
# 在 discovered_keywords 表中，
# 找出与目标词在同一时间窗口内同时出现在热榜的词
# 按共现频率排序，取 Top 10
related = SELECT name, co_appear_count
          FROM discovered_keywords
          WHERE date IN (target_keyword_hot_dates)
            AND name != target_keyword
          ORDER BY co_appear_count DESC
          LIMIT 10
```

展示：词 + 横向 bar（共现热度比例）+ 点击可直接搜索该词

**模块 E：平台分布**

今日该词热度在各平台的占比，环形图或横向条形图。
让用户一眼判断：这个词是"GitHub 开发者圈自嗨"还是"已破圈到大众平台"。

---

##### 8.3 历史数据回溯（搜新词时立即生成历史折线图）

**核心设计**：搜索一个从未追踪过的词时，不是显示空图等待积累，而是**立即向支持历史查询的数据源发起回溯请求**，当场生成尽可能完整的历史折线图。

---

**各数据源历史回溯能力对比**

| 数据源 | 可回溯时长 | 接口参数 | 能否立即生成历史图 |
|---|---|---|---|
| **GitHub star** | 仓库创建日至今（可达数年） | star-history API，一次返回全量 | ✅ 完整历史 |
| **Google Trends** | 2004 年至今 | pytrends `timeframe` 参数 | ✅ 完整历史（需代理） |
| **Hacker News** | 2006 年建站至今 | Algolia `dateRange` 参数 | ✅ 完整历史 |
| **npm 下载量** | 2015 年至今 | `downloads/range/{start}:{end}/{pkg}` | ✅ 完整历史 |
| **PyPI 下载量** | 近 180 天 | pypistats overall API | ✅ 近半年 |
| **Stack Overflow** | 建站至今 | `fromdate`/`todate` 参数 | ✅ 完整历史 |
| **Reddit** | 近期（Pushshift 受限后有限） | PRAW 时间范围搜索 | ⚠️ 近1年内 |
| **Dev.to** | 建站至今 | `published_at` 过滤 | ✅ 近数年 |
| **微博热搜** | 无历史接口 | — | ❌ 只能从今日起积累 |
| **知乎热榜** | 无历史接口 | — | ❌ 只能从今日起积累 |
| **今日头条** | 无历史接口 | — | ❌ 只能从今日起积累 |
| **B站热搜** | 无历史接口 | — | ❌ 只能从今日起积累 |
| **NewsNow 覆盖的国内平台** | 只返回当前实时榜单 | — | ❌ 只能从今日起积累 |

---

**历史回溯流程**

```
用户搜索 "openclaw"（本地无历史数据）
            ↓
并发发起多路历史查询（timeout 各自 10s）：

┌─────────────────────────────────────────────────────┐
│ 通道 1：GitHub star-history API                      │
│   → 返回仓库创建至今每日 star 增量                   │
│   → 写入 trend_data，source="github_star_history"   │
│   → 预计耗时：1-3s                                  │
├─────────────────────────────────────────────────────┤
│ 通道 2：Google Trends pytrends                       │
│   → 返回近5年搜索指数（0-100归一化）                 │
│   → 写入 trend_data，source="google_trends_history" │
│   → 预计耗时：2-5s（需代理则跳过）                  │
├─────────────────────────────────────────────────────┤
│ 通道 3：HackerNews Algolia API                       │
│   → 按月分批查询过去12个月的帖子数量                 │
│   → 写入 trend_data，source="hn_history"            │
│   → 预计耗时：2-4s（12次请求并发）                  │
├─────────────────────────────────────────────────────┤
│ 通道 4：npm / PyPI / Stack Overflow（如适用）        │
│   → 各自查询历史下载量/问题数                        │
│   → 写入对应 source 字段                            │
│   → 预计耗时：1-3s                                  │
├─────────────────────────────────────────────────────┤
│ 通道 5：NewsNow 实时快照（国内平台）                 │
│   → 只能拿到当前热度，无历史                         │
│   → 写入 trend_data，source="newsnow_snapshot"      │
│   → 在图表上显示为"今日数据点"                      │
└─────────────────────────────────────────────────────┘
            ↓
流式渲染（Progressive Loading）：
  t=0s：页面骨架 + 加载动画
  t=1-3s：GitHub star 历史线先出现（通常最快）
  t=2-5s：HN/npm 历史线追加
  t=3-8s：Google Trends 线追加（如可用）
  t=任意：国内平台当日数据点落点
  → 加载完的数据先渲染，不等所有数据就绪
            ↓
写入数据库，标记 source_type="historical_backfill"
加入 keywords 追踪列表（后续定时增量更新）
```

---

**图表渲染区分两类数据**

```
热度趋势 —— openclaw

200 │                                   ╭──╮
    │                              ╭────╯  ╰─╮
100 │                        ╭─────╯          ╰── ← GitHub star（历史回溯 ✓）
    │                   ╭────╯
  0 │──────────────────╯
    2025-01    2025-07    2026-01    2026-03

    ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ●  ← 微博热度（● 今日，虚线=积累中）

图例：
  ── 已回溯历史数据    · · 待积累（今日起）    ● 当日快照
```

视觉规则：
- 有历史数据的线：实线，颜色饱和
- 无历史、仅今日快照：单个数据点（实心圆点），带 "今日起积累" tooltip
- 历史回溯中（加载中）：虚线骨架 + shimmer 动画
- 回溯失败：灰色虚线 + "数据不可用" 标注，hover 显示原因

---

**历史回溯的时间桶聚合**

各平台数据粒度不同，统一聚合到「天」或「周」：

```python
def aggregate_to_bucket(raw_data: list, bucket: str = "day") -> list:
    """
    将不同粒度的原始数据聚合到统一时间桶
    bucket: "day" | "week" | "month"
    """
    if bucket == "day":
        return group_by_date(raw_data, sum)      # 当天内合并求和
    elif bucket == "week":
        return group_by_week(raw_data, sum)      # 周内合并求和
    elif bucket == "month":
        return group_by_month(raw_data, mean)    # 月内取均值

# GitHub star：原始是每天累计值，需先差分得到每日新增
def github_star_to_daily_delta(cumulative: list) -> list:
    return [cumulative[i] - cumulative[i-1] for i in range(1, len(cumulative))]

# Google Trends：原始是0-100相对指数，直接用
# HackerNews：原始是每次请求的帖子总数，直接用
# npm：原始是每日绝对下载量，直接用
```

---

**回溯结果写入数据库规范**

```sql
-- source 字段命名规范
-- 实时采集：    "weibo"、"zhihu"、"github_star"（无后缀）
-- 历史回溯：    "github_star_history"、"google_trends_history"（加 _history 后缀）
-- 今日快照：    "newsnow_snapshot"、"weibo_snapshot"（加 _snapshot 后缀）

-- trend_data 新增字段（在原有表基础上）
ALTER TABLE trend_data ADD COLUMN
    source_type TEXT DEFAULT 'realtime';
    -- 'realtime'：定时采集  'backfill'：历史回溯  'snapshot'：冷启动快照
```

---

##### 8.4 搜索冷启动完整流程（含历史回溯）

```
用户搜索词，回车
      ↓
Step 1：查本地 trend_data
      ↓
┌──────────────────────┬──────────────────────────────────────┐
│  有历史数据           │  无历史数据                           │
│  直接渲染完整页面     │  ↓ 进入冷启动                        │
└──────────────────────┘                                      │
                         Step 2：并发两组请求                  │
                                                              │
                         【历史回溯组】异步，可能耗时 3-8s     │
                         · GitHub star-history（仓库类词必做） │
                         · Google Trends（通用词，需代理）     │
                         · HackerNews（技术词）                │
                         · npm/PyPI（包名类词）                │
                         · Stack Overflow（技术词）            │
                                                              │
                         【实时快照组】优先返回，1-2s          │
                         · NewsNow → 各平台当前热度           │
                         · RSS → 近7日相关新闻               │
                                                              │
                         Step 3：流式渲染                      │
                         → 实时快照数据先到先渲染              │
                         → 历史数据到达后追加到折线图          │
                         → 「历史数据加载中...」进度提示       │
                                                              │
                         Step 4：持久化                        │
                         → 全部写入数据库                     │
                         → 加入追踪列表                       │
                         → 后续定时任务继续增量采集            │
└──────────────────────────────────────────────────────────────┘
```

---

##### 8.5 搜索建议（自动补全）

- 输入 2 个字符后触发
- 来源 1：`discovered_keywords` 表（按热度分降序）
- 来源 2：`keywords` 表中已追踪的词（标注「追踪中」）
- 候选项展示：词名 + 今日热度分 + 出现平台 tag
- 支持键盘上下键导航 + 回车确认

---

##### 8.6 新增数据库表

```sql
-- 新闻/内容条目表（模块 C 的数据源）
CREATE TABLE news_items (
    id           INTEGER PRIMARY KEY,
    keyword_id   INTEGER REFERENCES keywords(id),
    source       TEXT NOT NULL,       -- 'weibo' | 'zhihu' | 'bilibili' | 'github' | 'news'
    source_type  TEXT DEFAULT 'realtime',  -- 'realtime' | 'backfill' | 'snapshot'
    title        TEXT NOT NULL,
    url          TEXT,
    summary      TEXT,                -- 摘要，最多 200 字
    author       TEXT,
    hot_value    TEXT,                -- 平台原始热度值（如"156万"）
    rank_in_platform INTEGER,         -- 在平台热榜中的排名
    likes        INTEGER,
    comments     INTEGER,
    pub_date     DATETIME,            -- 内容发布时间
    fetched_at   DATETIME DEFAULT NOW(),
    UNIQUE(url)                       -- URL 去重
);

-- 相关词关联表（模块 D 的数据源）
CREATE TABLE keyword_relations (
    id              INTEGER PRIMARY KEY,
    keyword_a       TEXT NOT NULL,
    keyword_b       TEXT NOT NULL,
    co_appear_count INTEGER DEFAULT 1,  -- 共同出现在热榜的次数
    last_seen       DATE,
    UNIQUE(keyword_a, keyword_b)
);
```

---

##### 8.7 新增 API 接口

```
GET  /api/search?q=openclaw&days=30
     → 触发冷启动（如需），立即返回实时快照，历史回溯异步进行

GET  /api/search/{keyword}/backfill_status
     → 查询历史回溯进度（各数据源完成状态）
     → 前端轮询此接口，实时更新折线图

GET  /api/search/suggest?q=open
     → 搜索建议，返回候选词列表

GET  /api/search/{keyword}/news?source=all&days=7&page=1
     → 获取相关新闻列表，支持平台筛选和分页

GET  /api/search/{keyword}/related
     → 获取相关词列表

GET  /api/search/{keyword}/snapshot
     → 获取今日数据快照（数值卡片数据）

GET  /api/search/{keyword}/distribution
     → 获取今日各平台热度分布占比
```

**搜索接口完整响应结构**：
```json
{
  "keyword": "openclaw",
  "is_tracked": true,
  "snapshot": {
    "score": 8420,
    "score_delta": "+23%",
    "github_star_today": 1203,
    "platform_mentions": 12,
    "news_count": 47,
    "peak_platform": "微博"
  },
  "trend": {
    "period": { "start": "2026-02-15", "end": "2026-03-17" },
    "sources": {
      "github_star": [ { "date": "...", "value": 1203 } ],
      "weibo":       [ { "date": "...", "value": 8 } ]
    },
    "annotations": [
      { "date": "2026-03-02", "title": "登顶 GitHub Star 榜" }
    ]
  },
  "news": [
    {
      "source": "weibo",
      "title": "openclaw日活突破百万",
      "url": "https://...",
      "summary": "据报道...",
      "hot_value": "156万",
      "rank": 3,
      "pub_date": "2026-03-16T14:32:00"
    }
  ],
  "related_keywords": [
    { "name": "claude code", "co_appear_count": 18, "score": 72 },
    { "name": "AI Agent",    "co_appear_count": 14, "score": 68 }
  ],
  "distribution": {
    "weibo": 35,
    "zhihu": 28,
    "toutiao": 18,
    "bilibili": 14,
    "other": 5
  }
}
```

---

## 三、非功能需求

| 项目 | 要求 |
|---|---|
| 部署方式 | 支持 Docker 一键部署，也可 Vercel 前端 + Railway 后端分离部署 |
| 数据存储 | 本地 SQLite（单机）或 Supabase（云端免费版） |
| 响应速度 | 图表加载 < 2s（数据已缓存情况下） |
| 历史数据 | 从部署日起开始积累，支持无限期保存 |
| 国际化 | 中文优先，代码注释英文，预留 i18n 结构 |
| 开源协议 | MIT |

---

## 四、技术架构

### 4.1 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                      前端 (Next.js)                      │
│  搜索结果页  发现页  折线图看板  关键词管理  事件标注    │
│  [折线图][数据快照][相关新闻][相关词][平台分布]          │
└───────────────────────────┬──────────────────────────────┘
                            │ REST API
┌───────────────────────────▼──────────────────────────────┐
│                     后端 (FastAPI)                       │
│  搜索路由  发现引擎  新闻聚合  数据聚合  推送服务        │
│  数据源适配器层（插件式，每个数据源独立适配器）          │
└──────────┬────────────────────────────┬──────────────────┘
           │                            │
┌──────────▼──────────┐    ┌────────────▼──────────────────────────┐
│   数据库             │    │   采集调度器 (APScheduler)            │
│   SQLite / Supabase  │    │   ① 每小时：NewsNow + 热词提取        │
│                      │    │   ② 每日：GitHub/npm/PyPI/RSS 等      │
│ keywords             │    │   ③ 按需：冷启动实时采集              │
│ trend_data           │    └────┬──────────────────────────────────┘
│ news_items           │         │ 并发采集（各适配器独立限流）
│ keyword_relations    │    ┌────┴──────────────────────────────────┐
│ discovered_kw        │    │  【底座】NewsNow API/MCP（40+平台）   │
│ user_weight_presets  │    │          GitHub REST API              │
│ annotations          │    │  【开发者】npm · PyPI · Docker Hub    │
│ collect_logs         │    │           HackerNews · ProductHunt    │
└──────────────────────┘    │           StackOverflow · Dev.to      │
                            │  【搜索】 Google Trends · Bing API    │
                            │  【国际】 Reddit · YouTube            │
                            │  【RSS】  掘金·少数派·36kr·虎嗅·V2EX │
                            │  【补全】 star-history API            │
                            └───────────────────────────────────────┘
```

### 4.2 技术栈选型

**前端**
```
框架：Next.js 14 (App Router)
图表：Chart.js 4 + chartjs-plugin-annotation（事件标注）
样式：Tailwind CSS
状态：Zustand
部署：Vercel（免费）
```

**后端**
```
框架：FastAPI (Python)
调度：APScheduler（定时采集任务）
HTTP：httpx（异步请求）
部署：Railway / Docker
```

**数据库**
```
单机版：SQLite + SQLAlchemy ORM
云端版：Supabase（PostgreSQL，免费 500MB）
缓存：内存 TTL 缓存（避免重复调 API）
```

**数据采集**
```
底座：    NewsNow MCP Server（newsnow-mcp-server）或自部署实例 REST API
          GitHub REST API（Token 5000次/小时）
开发者：  npm registry API · pypistats API · Docker Hub API
          HackerNews Algolia API · Stack Exchange API · Dev.to API
          Product Hunt GraphQL API
搜索：    pytrends（Google Trends，需代理）· Bing Search API
国际社交：PRAW（Reddit）· YouTube Data API
RSS补充： feedparser 库，统一解析掘金/少数派/36kr/虎嗅/V2EX
历史补全：star-history API（GitHub star 全量历史）
```

### 4.3 数据库表设计

```sql
-- 关键词表
CREATE TABLE keywords (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,   -- 关键词文本
    type        TEXT DEFAULT 'word',    -- 'word' | 'github_repo'
    github_repo TEXT,                   -- 仅 type=github_repo 时使用
    group_name  TEXT,                   -- 分组名称
    created_at  DATETIME DEFAULT NOW(),
    is_active   BOOLEAN DEFAULT TRUE
);

-- 热度数据表（核心）
CREATE TABLE trend_data (
    id          INTEGER PRIMARY KEY,
    keyword_id  INTEGER REFERENCES keywords(id),
    source      TEXT NOT NULL,          -- 'github_star' | 'weibo' | 'zhihu' | 'google' ...
    date        DATE NOT NULL,          -- 精确到天
    hour        INTEGER,                -- 精确到小时（部分平台）
    value       REAL NOT NULL,          -- 热度值（各平台单位不同）
    raw_json    TEXT,                   -- 原始数据备份
    created_at  DATETIME DEFAULT NOW(),
    UNIQUE(keyword_id, source, date, hour)
);

-- 事件标注表
CREATE TABLE annotations (
    id          INTEGER PRIMARY KEY,
    keyword_id  INTEGER REFERENCES keywords(id),
    date        DATE NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,
    created_at  DATETIME DEFAULT NOW()
);

-- 采集任务日志表
CREATE TABLE collect_logs (
    id          INTEGER PRIMARY KEY,
    source      TEXT NOT NULL,
    keyword_id  INTEGER,
    status      TEXT,                   -- 'success' | 'failed' | 'skipped'
    message     TEXT,
    duration_ms INTEGER,
    created_at  DATETIME DEFAULT NOW()
);

-- 新闻/内容条目表（搜索结果页相关新闻模块）
CREATE TABLE news_items (
    id               INTEGER PRIMARY KEY,
    keyword_id       INTEGER REFERENCES keywords(id),
    source           TEXT NOT NULL,    -- 'weibo'|'zhihu'|'bilibili'|'github'|'news'
    title            TEXT NOT NULL,
    url              TEXT,
    summary          TEXT,             -- 摘要，最多 200 字
    author           TEXT,
    hot_value        TEXT,             -- 平台原始热度值（如"156万"）
    rank_in_platform INTEGER,          -- 在平台热榜中的排名
    likes            INTEGER,
    comments         INTEGER,
    pub_date         DATETIME,         -- 内容发布时间
    fetched_at       DATETIME DEFAULT NOW(),
    UNIQUE(url)
);

-- 相关词关联表（搜索结果页相关词模块）
CREATE TABLE keyword_relations (
    id              INTEGER PRIMARY KEY,
    keyword_a       TEXT NOT NULL,
    keyword_b       TEXT NOT NULL,
    co_appear_count INTEGER DEFAULT 1, -- 共同出现在热榜的次数
    last_seen       DATE,
    UNIQUE(keyword_a, keyword_b)
);

-- 用户权重预设表（折线图自定义权重功能）
CREATE TABLE user_weight_presets (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,           -- 预设名称，如"技术圈关注度"
    weights     TEXT NOT NULL,           -- JSON，如 {"github_star":0.5,"weibo":0.3}
    is_default  BOOLEAN DEFAULT FALSE,
    created_at  DATETIME DEFAULT NOW()
);
```

### 4.4 核心 API 接口

```
GET  /api/keywords                           获取所有关键词列表
POST /api/keywords                           添加关键词
DEL  /api/keywords/{id}                      删除关键词

-- 搜索结果页（F8）
GET  /api/search?q=openclaw&days=30          触发冷启动，返回完整结果页数据
GET  /api/search/suggest?q=open              搜索建议（自动补全）
GET  /api/search/{keyword}/news              获取相关新闻，支持 source/days/page 参数
GET  /api/search/{keyword}/related           获取相关词列表
GET  /api/search/{keyword}/snapshot          获取今日数据快照（数值卡片）
GET  /api/search/{keyword}/distribution      获取今日各平台热度分布占比

-- 热词发现（F7）
GET  /api/discover?date=today&limit=20       获取热词发现列表（今日飙升词）
GET  /api/discover/history?days=7            获取近7天发现的词列表
POST /api/discover/{name}/track              将发现的词加入追踪

-- 折线图看板（F1）
GET  /api/trends?keywords=A,B&days=30        获取折线图原始数据（各平台分开）
GET  /api/trends/composite                   计算综合指数曲线（传入权重配置）
     ?keywords=A,B&days=30
     &weights={"github_star":0.3,"weibo":0.2,...}
GET  /api/trends/{keyword_id}/sources        获取某词的各平台数据明细

-- 权重预设（F1）
GET  /api/weight-presets                     获取用户保存的权重预设列表
POST /api/weight-presets                     保存新的权重预设
PUT  /api/weight-presets/{id}               更新已有权重预设
DEL  /api/weight-presets/{id}               删除权重预设

-- 事件标注（F4）
GET  /api/annotations?keyword_id=1           获取事件标注
POST /api/annotations                        添加事件标注

-- 数据导出（F5）
GET  /api/export?keywords=A,B&days=30        导出 CSV

-- 采集管理
POST /api/collect/trigger                    手动触发一次采集
GET  /api/collect/logs                       查看采集日志
```

**折线图数据接口响应示例：**
```json
{
  "period": { "start": "2026-02-15", "end": "2026-03-17" },
  "keywords": [
    {
      "name": "openclaw",
      "sources": {
        "github_star": [
          { "date": "2026-02-15", "value": 12000 },
          { "date": "2026-02-16", "value": 14500 }
        ],
        "weibo": [
          { "date": "2026-02-15", "value": 3 },
          { "date": "2026-02-16", "value": 5 }
        ]
      }
    }
  ],
  "annotations": [
    { "date": "2026-03-02", "title": "登顶 GitHub Star 榜" }
  ]
}
```

---

## 五、参考项目与借鉴点

### 5.1 已调研项目

| 项目 | 借鉴内容 | 链接 |
|---|---|---|
| **NewsNow** | 40+ 平台数据源底座，官方 MCP Server，自托管友好，直接作为数据接入层 | https://github.com/ourongxing/newsnow |
| **GitTrends (ClickHouse)** | 折线图 UI 交互设计，多关键词对比模式 | https://gittrends.clickhouse.com |
| **star-history** | GitHub 项目 star 历史数据方案 | https://star-history.com |
| **daily-stars-explorer** | 每日 star 增量数据获取逻辑 | https://github.com/emanuelef/daily-stars-explorer |
| **joyce677/TrendRadar** | 热点推送架构参考（底层使用 NewsNow） | https://github.com/joyce677/TrendRadar |
| **sansan0/TrendRadar (原版)** | 关键词筛选逻辑、Docker 部署方案、MCP 集成 | https://github.com/sansan0/TrendRadar |
| **weibo-analysis-and-visualization** | pyecharts 时间序列折线图实现代码 | https://github.com/HUANGZHIHAO1994/weibo-analysis-and-visualization |
| **Calorific_value_calculation** | 热度值综合计算公式（评论量 + 增长率 + 媒体关注度） | https://github.com/shuita2333/Calorific_value_calculation |
| **StockPredict** | Django + Echarts 全栈架构验证 | https://github.com/Rockyzsu/StockPredict |
| **WeiboNewsProject** | 舆情系统整体设计思路 | https://github.com/gugug/WeiboNewsProject |
| **pytrends** | Google Trends 数据接入 | https://github.com/GeneralMills/pytrends |
| **EvanLi/Github-Ranking** | GitHub 各语言 Top100 数据结构参考 | https://github.com/EvanLi/Github-Ranking |

### 5.2 热度值归一化与权重策略

各数据源的量纲完全不同，系统通过两层处理统一展示：

```
第一层：各平台原始值 → 归一化到 [0, 100]
        方法：min-max 归一化，min/max 取该词该平台历史区间

第二层：各平台归一化值 → 按权重加权 → 综合指数
        权重：用户在 F1 权重配置面板中设定，支持预设保存

展示模式（用户可切换）：
  综合指数模式：一条加权合并曲线，Y 轴 0-100
  分平台模式：  多条独立曲线，双 Y 轴（社交 / GitHub）
  对数坐标：    右上角开关，适合量级差异极大场景
```

默认权重配置（按信号分组，可在设置中修改全局默认）：

| 分组 | 平台 | 默认权重 | 信号含义 |
|---|---|---|---|
| 开发者采用度 | GitHub star | 0.20 | 开发者关注度 |
| | npm 下载量 | 0.08 | JS 生态实际使用 |
| | PyPI 下载量 | 0.04 | Python 生态使用 |
| | Docker pull | 0.03 | 生产部署热度 |
| 社区讨论度 | Hacker News | 0.10 | 硅谷技术圈风向 |
| | 知乎 | 0.08 | 国内深度讨论 |
| | V2EX | 0.04 | 极客/独立开发者 |
| | Stack Overflow | 0.03 | 学习曲线指标 |
| 大众热搜 | 微博 | 0.12 | 国内大众破圈 |
| | 今日头条 | 0.08 | 资讯媒体覆盖 |
| 媒体覆盖度 | 36kr/虎嗅/少数派 | 0.10 | 科技媒体报道 |
| 内容扩散度 | B站/Dev.to | 0.10 | 视频/博客扩散 |
| 默认关闭 | Google Trends | 0.00 | 需代理，手动启用 |
| | Reddit/YouTube | 0.00 | 国际平台，按需启用 |

---

## 六、开发计划

### 阶段一：MVP（预计 2 周）

目标：跑通完整链路，GitHub 数据真实可用，搜索可用

```
Week 1：
├── Day 1-2   数据库设计（全部 8 张表）+ FastAPI 骨架 + 适配器接口定义
├── Day 3-4   GitHub API 采集模块（star 日增量 + star-history 历史补全）
├── Day 5     APScheduler 定时任务接入
└── Day 6-7   Next.js 前端 + 搜索框 + 折线图基础版（F8 冷启动流程）

Week 2：
├── Day 8     【方案 A】复用 TrendRadar main.py，插入数据库写入钩子
│             → 一次性接入 NewsNow 40+ 平台数据，写入 trend_data + news_items
├── Day 9     热词提取定时任务（F7）+ 相关词关联计算
├── Day 10    搜索结果页前端：快照卡片 + 相关新闻 + 平台分布图
├── Day 11    「发现」页面前端 + 多关键词叠加对比
├── Day 12    时间维度切换 + 折线图-新闻联动 + 权重配置面板（F1）
└── Day 13-14 Docker 打包 + 部署测试
```

交付物：可本地运行的 Docker 镜像，方案 A 数据采集跑通，搜索结果页五个模块可用

### 阶段二：完善（预计 2 周）

```
数据采集升级：
├── 【方案 B】切换为直接调 NewsNow REST API（跳过 TrendRadar 层）
├── npm / PyPI / Docker Hub 适配器（低难度，先做）
├── HackerNews / StackOverflow / Dev.to 适配器
├── Google Trends 适配器（pytrends，配置代理）
├── Reddit 适配器（PRAW）
└── RSS 批量接入（feedparser，掘金/少数派/36kr/虎嗅/V2EX）

产品功能：
├── 热词评分算法优化（NLP 实体识别过滤噪音词）
├── 事件标注功能（F4）
├── 数据导出 CSV / PNG（F5）
├── 异常推送飞书 + Telegram（F6）
└── Vercel 前端 + Railway 后端云端部署
```

### 阶段三：增强（后续迭代）

```
数据采集升级：
├── 【方案 C】自部署 NewsNow Docker 实例（数据实时 2 分钟级别）
├── ProductHunt 适配器
├── YouTube Data API 适配器
└── Bing Search API 适配器

产品功能：
├── 热词关联图谱（同时期飙升词的关联关系可视化）
├── 热度预测（基于历史数据的简单趋势线）
└── 报告生成（周报 / 月报 PDF，含热词 Top10 + 折线图）
```

---

## 七、关键风险与应对

| 风险 | 概率 | 影响 | 应对方案 |
|---|---|---|---|
| NewsNow 公网实例限流或下线 | 中 | 高 | 阶段三切换方案 C 自部署；本地缓存最近数据 |
| TrendRadar main.py 格式变更（方案 A） | 低 | 中 | 写适配器隔离，且方案 A 只是 MVP 过渡，阶段二换方案 B |
| Google Trends 国内访问限制 | 高 | 中 | 标记为可选功能，提供代理配置入口，优先用 Bing API 替代 |
| GitHub API 限流（无 Token 60次/小时） | 高 | 中 | 默认使用 Token（5000次/小时），采集间隔 > 1分钟，本地缓存 |
| 各平台适配器因页面结构变更失效 | 中 | 低 | NewsNow 和 TrendRadar 社区会先修复；直接 API 接入的平台更稳定 |
| 历史数据缺失（上线前的数据没有） | 必然 | 中 | GitHub star 通过 star-history 补全；社交平台标注"从部署日起积累" |
| 搜索冷启动时延过高 | 中 | 中 | 异步加载，先返回 GitHub 数据，其余数据流式追加到页面 |
| 热词提取噪音多（无意义词） | 高 | 低 | 维护停用词表，阶段二引入 NLP 实体识别过滤 |

---

## 八、待决策事项

- [ ] **前端框架**：Next.js vs 纯 Vite + React（Next.js 更利于 SEO 和未来的 SSR，但更重）
- [ ] **图表库**：Chart.js vs Recharts vs ECharts（ECharts 功能最强但包体大）
- [ ] **数据库**：SQLite 单机版 vs Supabase 云端版（优先 SQLite，保持零依赖）
- [ ] **多 Y 轴 vs 归一化**：默认交互方式待 UI 原型确认后决定
- [ ] **是否开源**：MIT 开源 vs 私有（建议开源，借助社区反馈快速迭代）
- [ ] **项目名**：TrendScope / TrendLens / HeatMap / IndexHub（待定）

---

## 九、附录

### A. 微信指数 openclaw 案例还原

朋友截图（2026-02-15 至 2026-03-16）展示的是 openclaw 关键词在微信生态的热度：

```
2/15 - 2/28：平稳低热（约 500-2000万）
3/2：openclaw 登顶 GitHub Star 榜
3/5：热度开始爆发
3/11：峰值（约 1.6亿）
3/16：回落至 3655万
```

这个案例说明：如果我们同时有 GitHub star 日增量和微博/微信提及量的双线图，可以清晰看到"GitHub 爆发 → 中文社区跟进"的时间差，这正是本工具的核心价值。

### B. TrendRadar API 数据结构

`joyce677/TrendRadar` 的 `/api/trends.json` 返回格式：
```json
{
  "updateTime": "2026-03-17 10:00:00",
  "platforms": {
    "weibo": [
      { "title": "openclaw爆火", "rank": 3, "hot": "156万" },
      ...
    ],
    "zhihu": [...],
    "bilibili": [...]
  }
}
```

我们需要在此基础上：
1. 每小时拉取并存入数据库（加 `keyword` 匹配过滤）
2. 累积存储形成时序数据
3. 聚合后支持按天展示折线图

---

*文档维护：随开发进展持续更新*
