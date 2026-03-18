(function () {
  const RECENT_SEARCHES_KEY = "trendscope.recent-searches.v1";
  const LOCALE_KEY = "trendscope.locale.v1";
  const MAX_RECENT_SEARCHES = 10;
  const DEFAULT_PROVIDER_SMOKE_QUERY = "openai/openai-python";
  const DEFAULT_PERIOD = "30d";
  const DEFAULT_REPO_PERIOD = "all";
  const DEFAULT_LOCALE = "zh";
  const GITHUB_URL_RE = /^https?:\/\/(?:www\.)?github\.com\/([^/\s]+)\/([^/\s]+?)(?:\.git|\/)?$/i;
  const OWNER_REPO_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
  const MESSAGES = {
    zh: {
      document: { title: "TrendScope" },
      brand: { note: "仓库趋势与关键词时间线。" },
      nav: { search: "搜索", tracked: "追踪" },
      hero: {
        runtime: "Python 运行时",
        headline: "搜仓库、URL 或关键词。",
        description: "仓库查询返回 GitHub 历史与上下文，关键词查询返回当前快照与补回来的历史新闻线。",
        band_github: "GitHub URL",
        band_newsnow: "owner/repo",
        band_backfill: "普通关键词",
        scope_title: "输入规则",
        scope_github: "GitHub URL 会自动规范化成 owner/repo",
        scope_newsnow: "owner/repo 和明确的裸仓库名优先走仓库查询",
        scope_tracking: "普通关键词优先补当前快照、历史新闻和内容流",
        note_fast_title: "先返回什么",
        note_fast_body: "首包先给当前可用结果，不等全部来源回填完成。",
        note_trace_title: "为什么结果会继续变化",
        note_trace_body: "后续回填会继续补历史、内容和状态，失败信息也会留在页面上。",
      },
      search: {
        placeholder: "试试 openai/openai-python 或 MCP",
        submit: "搜索",
        searching: "搜索中...",
        failed: "搜索失败。",
        hint_repo: "GitHub URL 和 owner/repo 默认展开全历史；裸仓库名解析成仓库后也会自动切换。",
        hint_keyword: "普通关键词默认先看 30 天；首包先给当前快照，后台再补带时间的历史新闻。",
      },
      starter: {
        title: "从这三条路径开始",
        subtitle: "不知道该搜什么时，先从一个示例打开真实结果，再按你的目标改查询。",
        example_repo_badge: "裸仓库名",
        example_repo_title: "openclaw",
        example_repo_body: "验证仓库名自动识别，直接看 GitHub 历史线和最新内容。",
        example_owner_repo_badge: "owner/repo",
        example_owner_repo_title: "openai/openai-python",
        example_owner_repo_body: "标准仓库查询路径，适合直接看 star 曲线、PR、release 和 issue。",
        example_keyword_badge: "普通关键词",
        example_keyword_title: "mcp",
        example_keyword_body: "看当前快照、历史新闻线，以及最近抓到的内容条目。",
        promise_title: "你会拿到什么",
        promise_subtitle: "先把结果承诺讲清楚，再让用户自己决定输入类型。",
        promise_repo_kicker: "仓库查询",
        promise_repo_title: "GitHub 历史 + 最新上下文",
        promise_repo_body: "返回 star 日增曲线、相关 PR / issue / release，并叠加可用性状态。",
        promise_keyword_kicker: "关键词查询",
        promise_keyword_title: "当前快照 + 历史新闻线",
        promise_keyword_body: "返回平台数、命中条目、最近内容，以及按发布时间补出来的历史热度线。",
        promise_trace_kicker: "结果状态",
        promise_trace_title: "不等回填完成，也不隐藏失败",
        promise_trace_body: "首包先给你当前可用结果，后续回填继续补，失败信息和来源状态都直接展示。",
      },
      result: {
        kicker_repo: "仓库查询",
        kicker_keyword: "关键词查询",
        health_ready: "可直接看",
        health_backfill: "回填中",
        health_attention: "需要留意",
        deck_repo: "已拿到 GitHub 历史，当前页有 {count} 条相关内容；再往下看上下文和来源状态。",
        deck_keyword: "今天快照里有 {items} 条 NewsNow 条目，覆盖 {platforms} 个平台；再往下看历史新闻线是否已经补齐。",
        meta_period: "周期 {value}",
        meta_updated: "更新于 {value}",
        meta_items: "{count} 条相关内容",
        stat_today: "今日信号",
        stat_today_repo_detail: "GitHub Star 日增",
        stat_today_keyword_detail: "NewsNow 今日命中",
        stat_platforms: "平台覆盖",
        stat_platforms_detail: "NewsNow 平台数",
        stat_context: "相关内容",
        stat_context_detail: "当前结果里的内容条目",
        stat_timeline: "时间线",
        stat_timeline_repo_detail: "GitHub 历史点位",
        stat_timeline_keyword_detail: "历史新闻点位",
        stat_latest: "最新内容",
        stat_latest_detail: "当前页共有 {count} 条内容",
        status_tracking: "追踪状态",
        status_sources: "来源状态",
        status_backfill: "回填状态",
        status_backfill_idle: "本次没有额外后台回填任务。",
        status_backfill_detail: "{count} 个后台任务",
        status_sources_ready: "{ready}/{total} 个来源已就绪",
        status_sources_waiting: "{count} 个来源仍在等待",
        status_sources_failed: "{count} 个来源有异常",
        status_sources_na: "当前查询没有可用来源状态。",
        sources_all_ready: "全部来源已就绪。",
        trend_title_repo: "GitHub 历史线",
        trend_title_keyword: "历史新闻热度线",
      },
      period: { "7d": "7 天", "30d": "30 天", "90d": "90 天", all: "全部" },
      recent: {
        title: "最近搜索",
        subtitle: "仅保存在当前浏览器，最多 10 条。",
        clear: "清空",
      },
      tracked: {
        title: "追踪列表",
        subtitle: "FastAPI 直接提供的独立追踪页也复用这组数据。",
        empty: "还没有追踪词。先搜索，再把结果加入观察列表。",
        loading: "正在从本地数据库读取追踪词。",
        updated: "更新于 {value}",
        saving: "保存中...",
        untrack: "取消追踪",
        update_error: "更新追踪词失败。",
      },
      action: {
        refresh: "刷新",
        refreshing: "刷新中...",
        working: "处理中...",
        save: "保存中...",
      },
      scheduler: {
        title: "调度器控制",
        subtitle: "查看内置采集循环，并按需刷新状态快照。",
        loading: "正在从后端加载调度器快照。",
        unavailable: "调度器快照暂时不可用。",
        enabled: "启用状态",
        worker: "工作线程",
        interval: "执行间隔",
        last_status: "最近状态",
        last_started: "最近启动",
        backfill: "回填策略",
        enabled_detail: "由 SCHEDULER_ENABLED 控制。",
        worker_detail: "当前周期 {period}。",
        interval_detail: "初始延迟 {value}。",
        last_status_detail: "上次触发了 {count} 个关键词。",
        last_started_detail: "最近结束时间 {value}。",
        backfill_detail: "累计执行 {count} 轮。",
      },
      provider: {
        preflight_title: "Provider 预检",
        preflight_subtitle: "切到 real 或 auto 之前，先检查本地配置。",
        verify: "验证真实源",
        verifying: "验证中...",
        smoke_placeholder: "Smoke 查询，例如 openai/openai-python",
        force_search: "强制真实搜索",
        run_smoke: "运行 smoke",
        running_smoke: "运行中...",
        loading_summary: "正在从后端加载 provider 预检结果。",
        unavailable_summary: "Provider 预检暂时不可用。",
        verify_error: "验证 provider 连通性失败。",
        smoke_error: "运行 provider smoke 失败。",
        mode: "模式",
        real_configured: "真实源配置",
        issues: "问题",
        notes: "说明",
        probe: "探测",
        search: "搜索",
        availability: "数据可用性",
        next_steps: "后续动作",
        guide: "指引",
        no_endpoint: "无 endpoint",
        smoke_search_title: "Smoke 搜索",
        smoke_search_subtitle: "{query} · {period}",
        smoke_feedback: "搜索 {search_status}。探测模式 {probe_mode}。force_search {force_search}。",
        normalized: "归一化 {value}",
        trend_series: "趋势序列 {count}",
        content_items: "内容条目 {count}",
        force_search_label: "force_search {value}",
        next_steps_title: "Smoke 后续动作",
        next_steps_subtitle: "来自后端 smoke runner 的操作清单。",
        next_steps_empty: "当前 smoke 输出没有额外动作项。",
      },
      collect: {
        title: "手动采集",
        subtitle: "触发追踪刷新，或对指定 query 运行一次性采集。",
        query_placeholder: "可选：指定 query 做一次性 collect",
        backfill_now: "立即执行回填",
        tracked: "采集追踪列表",
        query: "采集该查询",
        query_required: "先输入一个 query，再运行一次性采集。",
        feedback: "已触发 {count} 次采集任务。",
        trigger_error: "触发采集失败。",
        runs_title: "最近采集记录",
        runs_subtitle: "后端 scheduler 和 backfill worker 最近的写入尝试。",
        loading_runs: "正在加载最近的采集记录。",
        no_runs: "还没有采集记录。",
        no_message: "暂无附加信息。",
        global_run: "全局任务",
        keyword_ref: "关键词 #{id}",
        status: "状态 {value}",
        tracked_state: "已追踪",
        untracked_state: "未追踪",
      },
      loading: {
        title: "正在加载搜索框架",
        subtitle: "首包应该先返回，历史回填随后完成。",
      },
      empty: {
        default: "优先使用 GitHub 直接路径开始，首次结果更强。普通关键词会先返回快照，再补历史新闻和内容流。",
      },
      content: {
        title: "相关内容流",
        subtitle: "与当前查询关联的最近条目。",
        no_items: "还没有 {source}内容。等该来源可用后，采集会把这里补齐。",
        no_summary: "暂时没有摘要。",
      },
      content_source: {
        all: "全部来源",
        newsnow: "NewsNow",
        github: "GitHub",
        google_news: "Google News",
      },
      snapshot: {
        title: "今日快照",
        subtitle: "只展示直接来源事实，不做综合评分。",
        github_delta: "GitHub Star 增量",
        newsnow_platforms: "NewsNow 平台数",
        newsnow_items: "NewsNow 条目数",
        updated_at: "最近更新时间",
      },
      availability: {
        title: "数据可用性",
        subtitle: "前端把部分成功视为正常状态。",
        backfill_job: "回填任务",
        no_detail: "暂无更多细节。",
      },
      status: {
        kind: "类型",
        track: "追踪",
        job: "任务",
        tracked: "已追踪",
        idle: "未追踪",
      },
      kind: {
        github_repo: "GitHub 仓库",
        keyword: "关键词",
      },
      heading: {
        default: "搜索一个仓库或关键词。",
        repo: "先看仓库信号，再看上下文。",
        keyword: "先看关键词历史，再看当前快照。",
      },
      trend: {
        subtitle: "周期 {period}。当前可见 {count} 个来源。",
        no_history: "还没有历史新闻点位。后台会继续补带发布时间的内容，再把线拉长。",
        one_point: "当前只有 1 个快照点位。若历史新闻还没补到，就会先从当前快照起步。",
        curve: "当前看到的是快照累计线，后续如果补到更多带时间的内容，会切成历史新闻线。",
        history_one_point: "已按带发布时间的内容回溯出历史，但目前只有 1 个点位。",
        history_curve: "历史新闻线已按内容发布时间补出，后续采集还会继续补齐。",
        no_visible: "当前还没有可见趋势线。普通关键词会先尝试按带发布时间的内容回溯；如果时间信息还不够，就先从今日快照起步。",
        points: "{count} 个点位",
      },
      source: { github: "GitHub", newsnow: "NewsNow", google_news: "Google News", keyword_history: "历史新闻" },
      task_type: { history: "历史", content: "内容", snapshot: "快照" },
      source_type: {
        github_repo: "GitHub 仓库",
        keyword: "关键词",
        timeline: "内容时间线",
        archive: "历史抓取",
      },
      metric_label: {
        hot_hit_count: "热度条目",
        matched_item_count: "匹配条目",
        star_delta: "Star 增量",
      },
      availability_key: {
        github_history: "GitHub 历史",
        github_content: "GitHub 内容",
        newsnow_snapshot: "NewsNow 快照",
      },
      status_value: {
        success: "成功",
        failed: "失败",
        partial: "部分成功",
        not_applicable: "不适用",
        pending: "等待中",
        running: "运行中",
        ready: "就绪",
        skipped: "跳过",
        warning: "警告",
        misconfigured: "配置缺失",
        fallback_only: "仅回退",
        mock_only: "仅 mock",
        active: "活跃",
        idle: "空闲",
      },
      generic: { na: "N/A", yes: "是", no: "否", milliseconds: "毫秒" },
      ribbon: {
        source: "{source} {task}",
      },
    },
    en: {
      document: { title: "TrendScope" },
      brand: { note: "Repository trends and keyword timelines." },
      nav: { search: "Search", tracked: "Tracked" },
      hero: {
        runtime: "Python Runtime",
        headline: "Search a repo, URL, or keyword.",
        description: "Repository queries return GitHub history and context. Keyword queries return a current snapshot plus backfilled news history.",
        band_github: "GitHub URL",
        band_newsnow: "owner/repo",
        band_backfill: "Plain keyword",
        scope_title: "Input rules",
        scope_github: "GitHub URLs are normalized into owner/repo automatically",
        scope_newsnow: "owner/repo and clear bare repo names prefer the repository path",
        scope_tracking: "Plain keywords backfill snapshot, historical news, and content first",
        note_fast_title: "What returns first",
        note_fast_body: "The first response returns current data before every source finishes backfilling.",
        note_trace_title: "Why the page keeps changing",
        note_trace_body: "Later backfill keeps filling history, content, and state, and failures stay visible on the page.",
      },
      search: {
        placeholder: "Try openai/openai-python or MCP",
        submit: "Search",
        searching: "Searching...",
        failed: "Search failed.",
        hint_repo: "GitHub URLs and owner/repo default to full history; bare repo names auto-switch after they resolve as repositories.",
        hint_keyword: "Plain keywords default to 30 days. The first response returns the live snapshot first, then dated history gets filled in behind it.",
      },
      starter: {
        title: "Start with one of these three paths",
        subtitle: "If you are unsure what to search, open one live example first and then adapt it to your own target.",
        example_repo_badge: "Bare repo name",
        example_repo_title: "openclaw",
        example_repo_body: "Validate automatic repo resolution and jump straight into GitHub history plus fresh repository context.",
        example_owner_repo_badge: "owner/repo",
        example_owner_repo_title: "openai/openai-python",
        example_owner_repo_body: "The standard repository path for star history, PRs, releases, and issues.",
        example_keyword_badge: "Plain keyword",
        example_keyword_title: "mcp",
        example_keyword_body: "See the live snapshot, historical news line, and the recent content items.",
        promise_title: "What you get back",
        promise_subtitle: "Set the result contract first, then let the user choose the input type.",
        promise_repo_kicker: "Repository query",
        promise_repo_title: "GitHub history + fresh context",
        promise_repo_body: "Return star delta history, related PR / issue / release items, and explicit availability state.",
        promise_keyword_kicker: "Keyword query",
        promise_keyword_title: "Live snapshot + news history",
        promise_keyword_body: "Return platform count, hit count, recent content, and a historical line backfilled from publish times.",
        promise_trace_kicker: "Result state",
        promise_trace_title: "No waiting for full backfill, no hidden failures",
        promise_trace_body: "The first response returns current data immediately, later backfill keeps filling in, and failure state stays visible.",
      },
      result: {
        kicker_repo: "Repository query",
        kicker_keyword: "Keyword query",
        health_ready: "Ready to read",
        health_backfill: "Backfilling",
        health_attention: "Needs attention",
        deck_repo: "GitHub history is ready. This page already has {count} related item(s); use the sections below for context and source state.",
        deck_keyword: "Today's snapshot has {items} NewsNow item(s) across {platforms} platform(s); check below to see whether the historical line is filling in.",
        meta_period: "Period {value}",
        meta_updated: "Updated {value}",
        meta_items: "{count} related item(s)",
        stat_today: "Current signal",
        stat_today_repo_detail: "GitHub star delta today",
        stat_today_keyword_detail: "NewsNow hits today",
        stat_platforms: "Platforms",
        stat_platforms_detail: "NewsNow platforms",
        stat_context: "Context",
        stat_context_detail: "Content items in this result",
        stat_timeline: "Timeline",
        stat_timeline_repo_detail: "GitHub history points",
        stat_timeline_keyword_detail: "Historical news points",
        stat_latest: "Latest item",
        stat_latest_detail: "{count} content item(s) on page",
        status_tracking: "Tracking",
        status_sources: "Sources",
        status_backfill: "Backfill",
        status_backfill_idle: "No additional background backfill task for this response.",
        status_backfill_detail: "{count} background task(s)",
        status_sources_ready: "{ready}/{total} source(s) ready",
        status_sources_waiting: "{count} source(s) still waiting",
        status_sources_failed: "{count} source(s) have issues",
        status_sources_na: "No active source state for this query.",
        sources_all_ready: "All active sources are ready.",
        trend_title_repo: "GitHub history line",
        trend_title_keyword: "Historical news line",
      },
      period: { "7d": "7 days", "30d": "30 days", "90d": "90 days", all: "All" },
      recent: {
        title: "Recent searches",
        subtitle: "Stored locally in this browser, up to 10 entries.",
        clear: "Clear",
      },
      tracked: {
        title: "Tracked watchlist",
        subtitle: "The FastAPI-served /tracked page reuses the same dataset.",
        empty: "No tracked keyword yet. Search first, then promote the result into the watchlist.",
        loading: "Loading tracked keywords from the local database.",
        updated: "Updated {value}",
        saving: "Saving...",
        untrack: "Untrack",
        update_error: "Failed to update tracked keyword.",
      },
      action: {
        refresh: "Refresh",
        refreshing: "Refreshing...",
        working: "Working...",
        save: "Saving...",
      },
      scheduler: {
        title: "Scheduler control",
        subtitle: "Inspect the built-in collector loop and refresh its snapshot on demand.",
        loading: "Loading scheduler snapshot from the backend.",
        unavailable: "Scheduler snapshot is not available yet.",
        enabled: "Enabled",
        worker: "Worker",
        interval: "Interval",
        last_status: "Last status",
        last_started: "Last started",
        backfill: "Backfill",
        enabled_detail: "Controlled by SCHEDULER_ENABLED.",
        worker_detail: "Period {period}.",
        interval_detail: "Initial delay {value}.",
        last_status_detail: "Triggered {count} keyword(s) last time.",
        last_started_detail: "Last finished {value}.",
        backfill_detail: "Iterations {count}.",
      },
      provider: {
        preflight_title: "Provider preflight",
        preflight_subtitle: "Local configuration check before you switch to real or auto provider mode.",
        verify: "Verify real",
        verifying: "Verifying...",
        smoke_placeholder: "Smoke query, e.g. openai/openai-python",
        force_search: "Force real search",
        run_smoke: "Run smoke",
        running_smoke: "Running...",
        loading_summary: "Loading provider preflight from the backend.",
        unavailable_summary: "Provider preflight is not available yet.",
        verify_error: "Failed to verify provider connectivity.",
        smoke_error: "Failed to run provider smoke.",
        mode: "Mode",
        real_configured: "Real configured",
        issues: "Issues",
        notes: "Notes",
        probe: "Probe",
        search: "Search",
        availability: "Availability",
        next_steps: "Next steps",
        guide: "Guide",
        no_endpoint: "No endpoint",
        smoke_search_title: "Smoke search",
        smoke_search_subtitle: "{query} · {period}",
        smoke_feedback: "Search {search_status}. Probe {probe_mode}. force_search {force_search}.",
        normalized: "Normalized {value}",
        trend_series: "Trend series {count}",
        content_items: "Content items {count}",
        force_search_label: "force_search {value}",
        next_steps_title: "Smoke next steps",
        next_steps_subtitle: "Operator checklist from the backend smoke runner.",
        next_steps_empty: "No extra action items in the current smoke output.",
      },
      collect: {
        title: "Manual collect",
        subtitle: "Trigger tracked refreshes or run a one-off collection for a specific query.",
        query_placeholder: "Optional query for one-off collect",
        backfill_now: "Run backfill now",
        tracked: "Collect tracked",
        query: "Collect query",
        query_required: "Enter a query before running one-off collection.",
        feedback: "Triggered {count} collection run(s).",
        trigger_error: "Failed to trigger collection.",
        runs_title: "Recent collect runs",
        runs_subtitle: "Last write attempts recorded by the backend scheduler and backfill workers.",
        loading_runs: "Loading recent collect runs.",
        no_runs: "No collect runs recorded yet.",
        no_message: "No extra message recorded.",
        global_run: "Global run",
        keyword_ref: "Keyword #{id}",
        status: "Status {value}",
        tracked_state: "Tracked",
        untracked_state: "Not tracked",
      },
      loading: {
        title: "Loading search frame",
        subtitle: "The first response should land before history finishes backfilling.",
      },
      empty: {
        default: "Start with a direct GitHub path for the strongest first-run result. Plain keywords return a snapshot first, then fill in historical news and content.",
      },
      content: {
        title: "Context stream",
        subtitle: "Recent items associated with the current query.",
        no_items: "No {source}content items yet. Collection will populate this area when that source is available.",
        no_summary: "No summary available yet.",
      },
      content_source: {
        all: "All sources",
        newsnow: "NewsNow",
        github: "GitHub",
        google_news: "Google News",
      },
      snapshot: {
        title: "Today's readout",
        subtitle: "Simple source facts, no synthetic composite score.",
        github_delta: "GitHub star delta",
        newsnow_platforms: "NewsNow platforms",
        newsnow_items: "NewsNow items",
        updated_at: "Updated at",
      },
      availability: {
        title: "Availability",
        subtitle: "The UI treats partial success as normal.",
        backfill_job: "Backfill job",
        no_detail: "No additional detail provided.",
      },
      status: {
        kind: "Kind",
        track: "Track",
        job: "Job",
        tracked: "Tracked",
        idle: "Idle",
      },
      kind: {
        github_repo: "GitHub repo",
        keyword: "Keyword",
      },
      heading: {
        default: "Search one repository or keyword.",
        repo: "Repository intelligence, first.",
        keyword: "Keyword history first, snapshot second.",
      },
      trend: {
        subtitle: "Period {period}. {count} visible source(s).",
        no_history: "No historical news points yet. The backend will keep filling in dated content and extend the line.",
        one_point: "Only one snapshot point is visible right now. If dated history is still missing, the curve starts from the live snapshot first.",
        curve: "The current curve is still the accumulated snapshot view. Once more dated content lands, it will switch over to the historical news line.",
        history_one_point: "A first historical point was derived from dated content, but only one point is available so far.",
        history_curve: "The historical news line is backfilled from publish times, and later collections will keep extending it.",
        no_visible: "No visible trend line is ready yet. Plain keywords first try to backfill from dated content; if that is still sparse, the curve starts from today's snapshot.",
        points: "{count} points",
      },
      source: { github: "GitHub", newsnow: "NewsNow", google_news: "Google News", keyword_history: "News history" },
      task_type: { history: "history", content: "content", snapshot: "snapshot" },
      source_type: {
        github_repo: "GitHub repo",
        keyword: "Keyword",
        timeline: "Content timeline",
        archive: "Archive",
      },
      metric_label: {
        hot_hit_count: "Hit items",
        matched_item_count: "Matched items",
        star_delta: "Star delta",
      },
      availability_key: {
        github_history: "GitHub history",
        github_content: "GitHub content",
        newsnow_snapshot: "NewsNow snapshot",
      },
      status_value: {
        success: "success",
        failed: "failed",
        partial: "partial",
        not_applicable: "not applicable",
        pending: "pending",
        running: "running",
        ready: "ready",
        skipped: "skipped",
        warning: "warning",
        misconfigured: "misconfigured",
        fallback_only: "fallback only",
        mock_only: "mock only",
        active: "active",
        idle: "idle",
      },
      generic: { na: "N/A", yes: "yes", no: "no", milliseconds: "ms" },
      ribbon: {
        source: "{source} {task}",
      },
    },
  };

  function loadLocale() {
    try {
      const stored = window.localStorage.getItem(LOCALE_KEY);
      return stored === "en" ? "en" : DEFAULT_LOCALE;
    } catch (_) {
      return DEFAULT_LOCALE;
    }
  }

  function persistLocale() {
    try {
      window.localStorage.setItem(LOCALE_KEY, state.locale);
    } catch (_) {}
  }

  function resolveMessage(locale, key) {
    return key.split(".").reduce(function (value, part) {
      return value && typeof value === "object" ? value[part] : null;
    }, MESSAGES[locale]);
  }

  function interpolate(template, values) {
    return template.replace(/\{(\w+)\}/g, function (_, key) {
      return values[key] === undefined || values[key] === null ? "" : String(values[key]);
    });
  }

  function t(key, values) {
    const template = resolveMessage(state.locale, key) || resolveMessage("en", key) || key;
    return values ? interpolate(template, values) : template;
  }

  function translateToken(prefix, value) {
    const normalized = String(value).replaceAll("-", "_");
    return resolveMessage(state.locale, `${prefix}.${normalized}`) || resolveMessage("en", `${prefix}.${normalized}`) || String(value).replaceAll("_", " ");
  }

  const state = {
    locale: DEFAULT_LOCALE,
    view: "search",
    query: "",
    period: "30d",
    periodAuto: true,
    contentSource: "all",
    result: null,
    loading: false,
    error: null,
    trackingBusy: false,
    hiddenSeriesKeys: [],
    pollTimer: null,
    recentSearches: [],
    trackedKeywords: [],
    trackedLoading: false,
    trackedError: null,
    trackedBusyIds: [],
    schedulerStatus: null,
    schedulerLoading: false,
    schedulerError: null,
    providerStatus: null,
    providerLoading: false,
    providerError: null,
    providerVerifyBusy: false,
    providerVerifyFeedback: null,
    providerSmokeBusy: false,
    providerSmokeResult: null,
    providerSmokeQuery: DEFAULT_PROVIDER_SMOKE_QUERY,
    providerSmokePeriod: "30d",
    providerSmokeForceSearch: false,
    collectRuns: [],
    collectRunsLoading: false,
    collectRunsError: null,
    collectBusy: false,
    collectError: null,
    collectFeedback: null,
    collectResults: [],
    collectQuery: "",
    collectPeriod: "30d",
    collectRunBackfillNow: true,
  };

  let renderScheduled = false;
  let renderFrameHandle = 0;
  let syncedLocale = null;

  const elements = {
    searchViewLink: document.querySelector('[data-view-link="search"]'),
    trackedViewLink: document.querySelector('[data-view-link="tracked"]'),
    langZhButton: document.getElementById("lang-zh-button"),
    langEnButton: document.getElementById("lang-en-button"),
    heroSection: document.getElementById("hero-section"),
    secondaryGrid: document.getElementById("secondary-grid"),
    resultSummary: document.getElementById("result-summary"),
    resultKicker: document.getElementById("result-kicker"),
    resultHealthChip: document.getElementById("result-health-chip"),
    resultTitle: document.getElementById("result-title"),
    resultDeck: document.getElementById("result-deck"),
    resultMeta: document.getElementById("result-meta"),
    resultStats: document.getElementById("result-stats"),
    dashboard: document.getElementById("dashboard"),
    emptyState: document.getElementById("empty-state"),
    errorState: document.getElementById("error-state"),
    loadingPanel: document.getElementById("loading-panel"),
    queryInput: document.getElementById("query-input"),
    periodSelect: document.getElementById("period-select"),
    contentSourceSelect: document.getElementById("content-source-select"),
    searchButton: document.getElementById("search-button"),
    searchForm: document.getElementById("search-form"),
    starterGrid: document.getElementById("starter-grid"),
    starterActions: document.getElementById("starter-actions"),
    recentPanel: document.getElementById("recent-panel"),
    recentSearches: document.getElementById("recent-searches"),
    recentClearButton: document.getElementById("recent-clear-button"),
    trackedPanel: document.getElementById("tracked-panel"),
    trackedList: document.getElementById("tracked-list"),
    trackedEmptyState: document.getElementById("tracked-empty-state"),
    trackedRefreshButton: document.getElementById("tracked-refresh-button"),
    trackedError: document.getElementById("tracked-error"),
    operationsShell: document.getElementById("operations-shell"),
    operationsRefreshButton: document.getElementById("operations-refresh-button"),
    schedulerError: document.getElementById("scheduler-error"),
    schedulerStats: document.getElementById("scheduler-stats"),
    providerError: document.getElementById("provider-error"),
    providerVerifyButton: document.getElementById("provider-verify-button"),
    providerVerifyFeedback: document.getElementById("provider-verify-feedback"),
    providerSmokeForm: document.getElementById("provider-smoke-form"),
    providerSmokeQueryInput: document.getElementById("provider-smoke-query-input"),
    providerSmokePeriodSelect: document.getElementById("provider-smoke-period-select"),
    providerSmokeForceCheckbox: document.getElementById("provider-smoke-force-checkbox"),
    providerSmokeButton: document.getElementById("provider-smoke-button"),
    providerSmokeFeedback: document.getElementById("provider-smoke-feedback"),
    providerSummary: document.getElementById("provider-summary"),
    providerGrid: document.getElementById("provider-grid"),
    providerSmokeGrid: document.getElementById("provider-smoke-grid"),
    collectForm: document.getElementById("collect-form"),
    collectQueryInput: document.getElementById("collect-query-input"),
    collectPeriodSelect: document.getElementById("collect-period-select"),
    collectBackfillCheckbox: document.getElementById("collect-backfill-checkbox"),
    collectTrackedButton: document.getElementById("collect-tracked-button"),
    collectQueryButton: document.getElementById("collect-query-button"),
    collectError: document.getElementById("collect-error"),
    collectFeedback: document.getElementById("collect-feedback"),
    collectResults: document.getElementById("collect-results"),
    runsError: document.getElementById("runs-error"),
    collectRuns: document.getElementById("collect-runs"),
    statusRibbon: document.getElementById("status-ribbon"),
    trendHeading: document.getElementById("trend-heading"),
    trendSubtitle: document.getElementById("trend-subtitle"),
    trendNote: document.getElementById("trend-note"),
    trackButton: document.getElementById("track-button"),
    seriesLegend: document.getElementById("series-legend"),
    seriesGrid: document.getElementById("series-grid"),
    contentList: document.getElementById("content-list"),
    snapshotCards: document.getElementById("snapshot-cards"),
    availabilityList: document.getElementById("availability-list"),
  };

  function syncLocaleChrome() {
    if (syncedLocale === state.locale) {
      return;
    }
    syncedLocale = state.locale;
    document.documentElement.lang = state.locale === "zh" ? "zh-CN" : "en";
    document.title = t("document.title");
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      node.textContent = t(node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (node) {
      node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
    });
  }

  function parseLocationState() {
    state.view = window.location.pathname === "/tracked" ? "tracked" : "search";
    const params = new URLSearchParams(window.location.search);
    state.query = params.get("q") || "";
    state.periodAuto = !params.has("period");
    state.period = params.get("period") || getAutoPeriodForQuery(state.query);
    state.contentSource = params.get("content_source") || "all";
  }

  function syncControls() {
    if (elements.queryInput.value !== state.query) {
      elements.queryInput.value = state.query;
    }
    if (elements.periodSelect.value !== state.period) {
      elements.periodSelect.value = state.period;
    }
    if (elements.contentSourceSelect.value !== state.contentSource) {
      elements.contentSourceSelect.value = state.contentSource;
    }
    if (elements.collectQueryInput.value !== state.collectQuery) {
      elements.collectQueryInput.value = state.collectQuery;
    }
    if (elements.collectPeriodSelect.value !== state.collectPeriod) {
      elements.collectPeriodSelect.value = state.collectPeriod;
    }
    if (elements.collectBackfillCheckbox.checked !== state.collectRunBackfillNow) {
      elements.collectBackfillCheckbox.checked = state.collectRunBackfillNow;
    }
    if (elements.providerSmokeQueryInput.value !== state.providerSmokeQuery) {
      elements.providerSmokeQueryInput.value = state.providerSmokeQuery;
    }
    if (elements.providerSmokePeriodSelect.value !== state.providerSmokePeriod) {
      elements.providerSmokePeriodSelect.value = state.providerSmokePeriod;
    }
    if (elements.providerSmokeForceCheckbox.checked !== state.providerSmokeForceSearch) {
      elements.providerSmokeForceCheckbox.checked = state.providerSmokeForceSearch;
    }
  }

  function getBasePath() {
    return state.view === "tracked" ? "/tracked" : "/";
  }

  function setUrlState() {
    const params = new URLSearchParams();
    if (state.query) {
      params.set("q", state.query);
      params.set("period", state.period);
      if (state.contentSource !== "all") {
        params.set("content_source", state.contentSource);
      }
    }
    const search = params.toString();
    window.history.replaceState(null, "", search ? `${getBasePath()}?${search}` : getBasePath());
  }

  function navigateToView(view) {
    state.view = view;
    setUrlState();
    render();
  }

  function normalizeQuery(value) {
    return String(value || "").trim();
  }

  function isExplicitRepoQuery(query) {
    const normalized = normalizeQuery(query);
    return GITHUB_URL_RE.test(normalized) || OWNER_REPO_RE.test(normalized);
  }

  function getAutoPeriodForQuery(query, kindHint) {
    if (kindHint === "github_repo") {
      return DEFAULT_REPO_PERIOD;
    }
    if (kindHint === "keyword") {
      return DEFAULT_PERIOD;
    }
    return isExplicitRepoQuery(query) ? DEFAULT_REPO_PERIOD : DEFAULT_PERIOD;
  }

  function shouldAutoExpandRepoHistory(payload, requestedPeriod) {
    return Boolean(
      payload &&
      state.periodAuto &&
      requestedPeriod === DEFAULT_PERIOD &&
      payload.keyword &&
      payload.keyword.kind === "github_repo"
    );
  }

  function loadRecentSearches() {
    try {
      const stored = window.localStorage.getItem(RECENT_SEARCHES_KEY);
      if (!stored) {
        return [];
      }
      const parsed = JSON.parse(stored);
      return Array.isArray(parsed) ? parsed.slice(0, MAX_RECENT_SEARCHES) : [];
    } catch (_) {
      return [];
    }
  }

  function persistRecentSearches() {
    try {
      window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(state.recentSearches.slice(0, MAX_RECENT_SEARCHES)));
    } catch (_) {}
  }

  function rememberRecentSearch(payload) {
    const recentEntry = {
      query: payload.keyword.kind === "github_repo" ? payload.keyword.normalized_query : payload.keyword.raw_query,
      normalizedQuery: payload.keyword.normalized_query,
      kind: payload.keyword.kind,
      period: state.period,
      contentSource: state.contentSource,
    };

    state.recentSearches = [recentEntry]
      .concat(
        state.recentSearches.filter(
          (item) => `${item.kind}:${item.normalizedQuery}` !== `${recentEntry.kind}:${recentEntry.normalizedQuery}`
        )
      )
      .slice(0, MAX_RECENT_SEARCHES);
    persistRecentSearches();
  }

  function getTrackedQuery(item) {
    return item.kind === "github_repo" ? item.normalized_query : item.raw_query;
  }

  function formatTrackedKind(kind) {
    return translateToken("kind", kind);
  }

  async function loadTrackedKeywords() {
    state.trackedLoading = true;
    state.trackedError = null;
    render();

    try {
      state.trackedKeywords = await request("/api/keywords?tracked_only=true");
    } catch (error) {
      state.trackedError = error instanceof Error ? error.message : t("tracked.update_error");
    } finally {
      state.trackedLoading = false;
      render();
    }
  }

  async function loadOperationsData() {
    state.schedulerLoading = true;
    state.providerLoading = true;
    state.collectRunsLoading = true;
    state.schedulerError = null;
    state.providerError = null;
    state.collectRunsError = null;
    render();

    const [schedulerResult, providerResult, runsResult] = await Promise.allSettled([
      request("/api/collect/status"),
      request("/api/provider-status"),
      request("/api/collect/logs?limit=12"),
    ]);

    if (schedulerResult.status === "fulfilled") {
      state.schedulerStatus = schedulerResult.value;
    } else {
      state.schedulerStatus = null;
      state.schedulerError =
        schedulerResult.reason instanceof Error ? schedulerResult.reason.message : t("scheduler.unavailable");
    }

    if (runsResult.status === "fulfilled") {
      state.collectRuns = runsResult.value;
    } else {
      state.collectRuns = [];
      state.collectRunsError = runsResult.reason instanceof Error ? runsResult.reason.message : t("collect.trigger_error");
    }

    if (providerResult.status === "fulfilled") {
      state.providerStatus = providerResult.value;
    } else {
      state.providerStatus = null;
      state.providerError = providerResult.reason instanceof Error ? providerResult.reason.message : t("provider.smoke_error");
    }

    state.schedulerLoading = false;
    state.providerLoading = false;
    state.collectRunsLoading = false;
    render();
  }

  async function request(path, init) {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init && init.headers ? init.headers : {}),
      },
      cache: "no-store",
    });

    if (!response.ok) {
      let detail = "Request failed.";
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }

    return response.json();
  }

  function formatDate(value) {
    if (!value) {
      return t("generic.na");
    }
    return new Date(value).toLocaleString(state.locale === "zh" ? "zh-CN" : "en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatDuration(value) {
    if (value === null || value === undefined) {
      return t("generic.na");
    }
    return `${value} ${t("generic.milliseconds")}`;
  }

  function formatAvailabilityLabel(key) {
    return translateToken("availability_key", key);
  }

  function formatTaskLabel(task) {
    return t("ribbon.source", {
      source: translateToken("source", task.source),
      task: translateToken("task_type", task.task_type),
    });
  }

  function formatStatusLabel(value) {
    return translateToken("status_value", value);
  }

  function formatBooleanLabel(value) {
    return value ? t("generic.yes") : t("generic.no");
  }

  function formatContentSourceLabel(value) {
    return translateToken("content_source", value);
  }

  function formatPeriodLabel(value) {
    return translateToken("period", value);
  }

  function formatSourceTypeLabel(value) {
    return translateToken("source_type", value);
  }

  function formatMetricLabel(value) {
    return translateToken("metric_label", value);
  }

  function renderProviderCard(check) {
    const issuesMarkup = check.issues.length
      ? `
          <div class="provider-issues">
            <strong>${t("provider.issues")}</strong>
            <ul class="provider-list">
              ${check.issues.map((item) => `<li>${item}</li>`).join("")}
            </ul>
          </div>
        `
      : "";
    const notesMarkup = check.notes.length
      ? `
          <div class="provider-notes">
            <strong>${t("provider.notes")}</strong>
            <ul class="provider-list">
              ${check.notes.map((item) => `<li>${item}</li>`).join("")}
            </ul>
          </div>
        `
      : "";

    return `
      <article class="provider-card">
        <header>
          <div>
            <h3>${translateToken("source", check.source)}</h3>
            <p>${check.preferred_provider}${check.fallback_provider ? ` -> ${check.fallback_provider}` : ""}</p>
          </div>
          <span class="provider-chip">${formatStatusLabel(check.status)}</span>
        </header>
        <div class="provider-meta">
          <span>${t("provider.mode")} ${check.mode}</span>
          <span>${t("provider.real_configured")} ${formatBooleanLabel(check.can_use_real_provider)}</span>
        </div>
        ${issuesMarkup}
        ${notesMarkup}
      </article>
    `;
  }

  function renderProviderVerifyCard(result) {
    return `
      <article class="provider-card">
        <header>
          <div>
            <h3>${translateToken("source", result.source)}</h3>
            <p>${result.attempted_provider}</p>
          </div>
          <span class="provider-chip">${formatStatusLabel(result.status)}</span>
        </header>
        <div class="provider-meta">
          <span>${result.endpoint || t("provider.no_endpoint")}</span>
        </div>
        <div class="provider-notes">
          <strong>${t("provider.probe")}</strong>
          <ul class="provider-list">
            <li>${result.message}</li>
          </ul>
        </div>
      </article>
    `;
  }

  function renderProviderSmokeSearchCard(result) {
    const availabilityEntries = Object.entries(result.search.availability || {});
    const details = [
      result.search.message,
      result.search.keyword_kind ? `${t("status.kind")} ${translateToken("kind", result.search.keyword_kind)}` : null,
      result.search.normalized_query ? t("provider.normalized", { value: result.search.normalized_query }) : null,
      t("provider.trend_series", { count: result.search.trend_series_count }),
      t("provider.content_items", { count: result.search.content_item_count }),
      result.search.backfill_status ? `${t("availability.backfill_job")} ${formatStatusLabel(result.search.backfill_status)}` : null,
    ].filter(Boolean);
    const availabilityMarkup = availabilityEntries.length
      ? `
          <div class="provider-notes">
            <strong>${t("provider.availability")}</strong>
            <ul class="provider-list">
              ${availabilityEntries.map(([key, value]) => `<li>${formatAvailabilityLabel(key)}: ${formatStatusLabel(value)}</li>`).join("")}
            </ul>
          </div>
        `
      : "";

    return `
      <article class="provider-card provider-smoke-card">
        <header>
          <div>
            <h3>${t("provider.smoke_search_title")}</h3>
            <p>${t("provider.smoke_search_subtitle", { query: result.query, period: formatPeriodLabel(result.period) })}</p>
          </div>
          <span class="provider-chip">${formatStatusLabel(result.search.status)}</span>
        </header>
        <div class="provider-meta">
          <span>${t("provider.probe")} ${result.probe_mode}</span>
          <span>${t("provider.force_search_label", { value: formatBooleanLabel(result.force_search) })}</span>
        </div>
        <div class="provider-notes">
          <strong>${t("provider.search")}</strong>
          <ul class="provider-list">
            ${details.map((item) => `<li>${item}</li>`).join("")}
          </ul>
        </div>
        ${availabilityMarkup}
      </article>
    `;
  }

  function renderProviderSmokeNextStepsCard(result) {
    const nextSteps = result.next_steps.length ? result.next_steps : [t("provider.next_steps_empty")];

    return `
      <article class="provider-card provider-smoke-card">
        <header>
          <div>
            <h3>${t("provider.next_steps_title")}</h3>
            <p>${t("provider.next_steps_subtitle")}</p>
          </div>
          <span class="provider-chip">${t("provider.guide")}</span>
        </header>
        <div class="provider-notes">
          <strong>${t("provider.next_steps")}</strong>
          <ul class="provider-list">
            ${nextSteps.map((item) => `<li>${item}</li>`).join("")}
          </ul>
        </div>
      </article>
    `;
  }

  function getSeriesKey(series) {
    return `${series.source}-${series.metric}-${series.source_type}`;
  }

  function formatSeriesLabel(series) {
    return `${translateToken("source", series.source)} ${formatMetricLabel(series.metric)}`;
  }

  function getVisibleSeries() {
    if (!state.result) {
      return [];
    }
    return state.result.trend.series.filter((series) => !state.hiddenSeriesKeys.includes(getSeriesKey(series)));
  }

  function getHeading() {
    if (!state.result) {
      return t("heading.default");
    }
    return state.result.keyword.kind === "github_repo" ? t("heading.repo") : t("heading.keyword");
  }

  function getKeywordHistorySeries() {
    if (!state.result) {
      return null;
    }
    const matches = state.result.trend.series.filter(
      (series) => series.metric === "matched_item_count" && series.source_type === "timeline"
    );
    if (!matches.length) {
      return null;
    }
    return matches.reduce((best, series) => (series.points.length > best.points.length ? series : best));
  }

  function getTrendNote() {
    if (!state.result || state.result.keyword.kind !== "keyword") {
      return null;
    }
    const historySeries = getKeywordHistorySeries();
    if (historySeries) {
      if (historySeries.points.length === 1) {
        return t("trend.history_one_point");
      }
      return t("trend.history_curve");
    }
    const newsnowSeries = state.result.trend.series.find(
      (series) => series.source === "newsnow" && series.metric === "hot_hit_count"
    );
    if (!newsnowSeries) {
      return t("trend.no_history");
    }
    if (newsnowSeries.points.length === 1) {
      return t("trend.one_point");
    }
    return t("trend.curve");
  }

  function getDisplayQuery() {
    if (!state.result) {
      return "";
    }
    return state.result.keyword.kind === "github_repo" ? state.result.keyword.normalized_query : state.result.keyword.raw_query;
  }

  function formatMetricValue(value) {
    return value === null || value === undefined ? t("generic.na") : String(value);
  }

  function trimMessage(value, maxLength) {
    if (!value) {
      return "";
    }
    const normalized = String(value).replace(/\s+/g, " ").trim();
    if (normalized.length <= maxLength) {
      return normalized;
    }
    return `${normalized.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
  }

  function getPrimarySeries() {
    if (!state.result || !state.result.trend.series.length) {
      return null;
    }
    if (state.result.keyword.kind === "keyword") {
      const historySeries = getKeywordHistorySeries();
      if (historySeries) {
        return historySeries;
      }
    }
    const preferences =
      state.result.keyword.kind === "github_repo"
        ? [
            ["github", "star_delta"],
            ["newsnow", "hot_hit_count"],
          ]
        : [
            ["newsnow", "hot_hit_count"],
            ["github", "star_delta"],
          ];

    for (const [source, metric] of preferences) {
      const match = state.result.trend.series.find((series) => series.source === source && series.metric === metric);
      if (match) {
        return match;
      }
    }

    return state.result.trend.series[0];
  }

  function getLatestContentItem() {
    if (!state.result || !state.result.content_items.length) {
      return null;
    }
    const datedItems = state.result.content_items.filter((item) => item.published_at);
    if (!datedItems.length) {
      return state.result.content_items[0];
    }
    return datedItems.reduce((latest, item) =>
      new Date(item.published_at).getTime() > new Date(latest.published_at).getTime() ? item : latest
    );
  }

  function getAvailabilityCounts() {
    if (!state.result) {
      return { total: 0, ready: 0, waiting: 0, failed: 0 };
    }

    return Object.values(state.result.availability || {})
      .filter((value) => !["not_applicable", "skipped"].includes(value))
      .reduce(
        (counts, value) => {
          counts.total += 1;
          if (["ready", "success", "active"].includes(value)) {
            counts.ready += 1;
          } else if (["pending", "running", "partial", "warning"].includes(value)) {
            counts.waiting += 1;
          } else {
            counts.failed += 1;
          }
          return counts;
        },
        { total: 0, ready: 0, waiting: 0, failed: 0 }
      );
  }

  function getToneFromStatus(value) {
    if (["failed", "misconfigured", "warning", "fallback_only", "mock_only"].includes(value)) {
      return "attention";
    }
    if (["pending", "running", "partial"].includes(value)) {
      return "backfill";
    }
    if (["ready", "success", "active"].includes(value)) {
      return "ready";
    }
    return "neutral";
  }

  function getResultHealth() {
    const counts = getAvailabilityCounts();
    let tone = counts.failed > 0 ? "attention" : counts.waiting > 0 ? "backfill" : "ready";
    if (!counts.total && state.result && state.result.backfill_job) {
      tone = getToneFromStatus(state.result.backfill_job.status);
    }
    if (tone === "neutral") {
      tone = "ready";
    }
    return {
      tone,
      label: t(`result.health_${tone}`),
      availabilityCounts: counts,
    };
  }

  function getAvailabilityDetail(counts) {
    if (!counts.total) {
      return t("result.status_sources_na");
    }

    const details = [];
    if (counts.failed) {
      details.push(t("result.status_sources_failed", { count: counts.failed }));
    }
    if (counts.waiting) {
      details.push(t("result.status_sources_waiting", { count: counts.waiting }));
    }
    if (!counts.failed && !counts.waiting) {
      details.push(t("result.sources_all_ready"));
    }
    return details.join(" ");
  }

  function sparklineSvg(points) {
    if (!points.length) {
      return "";
    }
    const width = 640;
    const height = 92;
    const values = points.map((point) => point.value);
    const min = Math.min.apply(null, values);
    const max = Math.max.apply(null, values);
    const range = max - min || 1;
    const path = points
      .map((point, index) => {
        const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
        const y = height - ((point.value - min) / range) * (height - 10) - 5;
        return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");
    const area = `${path} L ${width} ${height} L 0 ${height} Z`;
    return `
      <svg class="sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
        <path class="sparkline-area" d="${area}"></path>
        <path class="sparkline-path" d="${path}"></path>
      </svg>
    `;
  }

  function renderNavigation() {
    elements.searchViewLink.classList.toggle("is-active", state.view === "search");
    elements.trackedViewLink.classList.toggle("is-active", state.view === "tracked");
    elements.langZhButton.classList.toggle("is-active", state.locale === "zh");
    elements.langEnButton.classList.toggle("is-active", state.locale === "en");
  }

  function renderResultSummary() {
    if (!state.result) {
      elements.resultSummary.classList.add("hidden");
      elements.resultStats.innerHTML = "";
      return;
    }

    const health = getResultHealth();
    const primarySeries = getPrimarySeries();
    const latestContentItem = getLatestContentItem();
    const resultUpdatedAt = state.result.snapshot.updated_at || state.result.keyword.updated_at;
    const timelinePoints = primarySeries ? primarySeries.points.length : null;
    const latestPublishedAt = latestContentItem ? formatDate(latestContentItem.published_at) : t("generic.na");
    const stats =
      state.result.keyword.kind === "github_repo"
        ? [
            {
              label: t("result.stat_today"),
              value: formatMetricValue(state.result.snapshot.github_star_today),
              detail: t("result.stat_today_repo_detail"),
            },
            {
              label: t("result.stat_context"),
              value: formatMetricValue(state.result.content_items.length),
              detail: t("result.stat_context_detail"),
            },
            {
              label: t("result.stat_timeline"),
              value: formatMetricValue(timelinePoints),
              detail: t("result.stat_timeline_repo_detail"),
            },
            {
              label: t("result.stat_latest"),
              value: latestPublishedAt,
              detail: t("result.stat_latest_detail", { count: state.result.content_items.length }),
            },
          ]
        : [
            {
              label: t("result.stat_today"),
              value: formatMetricValue(state.result.snapshot.newsnow_item_count),
              detail: t("result.stat_today_keyword_detail"),
            },
            {
              label: t("result.stat_platforms"),
              value: formatMetricValue(state.result.snapshot.newsnow_platform_count),
              detail: t("result.stat_platforms_detail"),
            },
            {
              label: t("result.stat_timeline"),
              value: formatMetricValue(timelinePoints),
              detail: t("result.stat_timeline_keyword_detail"),
            },
            {
              label: t("result.stat_latest"),
              value: latestPublishedAt,
              detail: t("result.stat_latest_detail", { count: state.result.content_items.length }),
            },
          ];

    elements.resultKicker.textContent =
      state.result.keyword.kind === "github_repo" ? t("result.kicker_repo") : t("result.kicker_keyword");
    elements.resultHealthChip.textContent = health.label;
    elements.resultHealthChip.dataset.tone = health.tone;
    elements.resultTitle.textContent = getDisplayQuery();
    elements.resultDeck.textContent =
      state.result.keyword.kind === "github_repo"
        ? t("result.deck_repo", { count: state.result.content_items.length })
        : t("result.deck_keyword", {
            items: state.result.snapshot.newsnow_item_count ?? 0,
            platforms: state.result.snapshot.newsnow_platform_count ?? 0,
          });
    elements.resultMeta.innerHTML = [
      `<span>${translateToken("kind", state.result.keyword.kind)}</span>`,
      `<span>${t("result.meta_period", { value: formatPeriodLabel(state.period) })}</span>`,
      `<span>${t("result.meta_updated", { value: formatDate(resultUpdatedAt) })}</span>`,
      `<span>${t("result.meta_items", { count: state.result.content_items.length })}</span>`,
    ].join("");
    elements.resultStats.innerHTML = stats
      .map(
        (item) => `
          <article class="result-stat">
            <span>${item.label}</span>
            <strong>${item.value}</strong>
            <p>${item.detail}</p>
          </article>
        `
      )
      .join("");
    elements.resultSummary.classList.remove("hidden");
  }

  function renderStatusRibbon() {
    if (!state.result) {
      elements.statusRibbon.classList.add("hidden");
      elements.statusRibbon.innerHTML = "";
      return;
    }

    const health = getResultHealth();
    const counts = health.availabilityCounts;
    const diagnostics = [
      {
        label: t("result.status_tracking"),
        value: state.result.keyword.is_tracked ? t("status.tracked") : t("status.idle"),
        detail: `${translateToken("kind", state.result.keyword.kind)} · ${t("result.meta_period", {
          value: formatPeriodLabel(state.period),
        })}`,
        tone: state.result.keyword.is_tracked ? "ready" : "neutral",
      },
      {
        label: t("result.status_sources"),
        value: counts.total ? t("result.status_sources_ready", { ready: counts.ready, total: counts.total }) : t("generic.na"),
        detail: getAvailabilityDetail(counts),
        tone: counts.total ? health.tone : "neutral",
      },
      {
        label: t("result.status_backfill"),
        value: state.result.backfill_job ? formatStatusLabel(state.result.backfill_job.status) : t("status_value.idle"),
        detail: state.result.backfill_job
          ? state.result.backfill_job.error_message
            ? trimMessage(state.result.backfill_job.error_message, 180)
            : t("result.status_backfill_detail", { count: state.result.backfill_job.tasks.length })
          : t("result.status_backfill_idle"),
        tone: state.result.backfill_job ? getToneFromStatus(state.result.backfill_job.status) : "neutral",
      },
    ];

    elements.statusRibbon.innerHTML = diagnostics
      .map(
        (item) => `
          <article class="diagnostic-card" data-tone="${item.tone}">
            <span>${item.label}</span>
            <strong>${item.value}</strong>
            <p>${item.detail}</p>
          </article>
        `
      )
      .join("");
    elements.statusRibbon.classList.remove("hidden");
  }

  function renderTrackedKeywords() {
    const shouldShowTrackedPanel =
      state.view === "tracked" || state.trackedLoading || Boolean(state.trackedError) || state.trackedKeywords.length > 0;
    elements.trackedPanel.classList.toggle("hidden", !shouldShowTrackedPanel);
    elements.trackedRefreshButton.disabled = state.trackedLoading || state.trackedBusyIds.length > 0;
    elements.trackedRefreshButton.textContent = state.trackedLoading ? t("action.refreshing") : t("action.refresh");

    if (state.trackedError) {
      elements.trackedError.textContent = state.trackedError;
      elements.trackedError.classList.remove("hidden");
    } else {
      elements.trackedError.textContent = "";
      elements.trackedError.classList.add("hidden");
    }

    if (state.trackedLoading && !state.trackedKeywords.length) {
      elements.trackedEmptyState.classList.add("hidden");
      elements.trackedList.innerHTML = `
        <div class="empty-state">
          ${t("tracked.loading")}
        </div>
      `;
      return;
    }

    if (!state.trackedKeywords.length) {
      elements.trackedList.innerHTML = "";
      elements.trackedEmptyState.classList.remove("hidden");
      return;
    }

    elements.trackedEmptyState.classList.add("hidden");
    elements.trackedList.innerHTML = state.trackedKeywords
      .map((item, index) => {
        const busy = state.trackedBusyIds.includes(item.id);
        return `
          <article class="tracked-item">
            <div class="tracked-item-copy">
              <button class="tracked-jump" data-tracked-open-index="${index}" type="button">${getTrackedQuery(item)}</button>
              <div class="tracked-meta">
                <span>${formatTrackedKind(item.kind)}</span>
                <span>${t("tracked.updated", { value: formatDate(item.updated_at) })}</span>
              </div>
            </div>
            <button class="button-ghost" data-tracked-id="${item.id}" type="button" ${busy ? "disabled" : ""}>
              ${busy ? t("tracked.saving") : t("tracked.untrack")}
            </button>
          </article>
        `;
      })
      .join("");
  }

  function renderOperations() {
    if (state.view !== "tracked") {
      elements.operationsShell.classList.add("hidden");
      return;
    }

    elements.operationsShell.classList.toggle("hidden", state.view !== "tracked");
    const operationsLoading = state.schedulerLoading || state.providerLoading || state.collectRunsLoading;
    const operationsBusy = operationsLoading || state.collectBusy || state.providerVerifyBusy || state.providerSmokeBusy;
    elements.operationsRefreshButton.disabled =
      operationsBusy;
    elements.operationsRefreshButton.textContent = operationsLoading
      ? t("action.refreshing")
      : operationsBusy
        ? t("action.working")
        : t("action.refresh");

    if (state.schedulerError) {
      elements.schedulerError.textContent = state.schedulerError;
      elements.schedulerError.classList.remove("hidden");
    } else {
      elements.schedulerError.textContent = "";
      elements.schedulerError.classList.add("hidden");
    }

    if (state.schedulerLoading && !state.schedulerStatus) {
      elements.schedulerStats.innerHTML = `
        <div class="empty-state">
          ${t("scheduler.loading")}
        </div>
      `;
    } else if (!state.schedulerStatus) {
      elements.schedulerStats.innerHTML = `
        <div class="empty-state">
          ${t("scheduler.unavailable")}
        </div>
      `;
    } else {
      const stats = [
        [t("scheduler.enabled"), formatBooleanLabel(state.schedulerStatus.enabled), t("scheduler.enabled_detail")],
        [
          t("scheduler.worker"),
          formatStatusLabel(state.schedulerStatus.running ? "running" : "idle"),
          t("scheduler.worker_detail", { period: formatPeriodLabel(state.schedulerStatus.period) }),
        ],
        [
          t("scheduler.interval"),
          `${state.schedulerStatus.interval_seconds}s`,
          t("scheduler.interval_detail", { value: `${state.schedulerStatus.initial_delay_seconds}s` }),
        ],
        [
          t("scheduler.last_status"),
          formatStatusLabel(state.schedulerStatus.last_status),
          state.schedulerStatus.last_error || t("scheduler.last_status_detail", { count: state.schedulerStatus.last_triggered_count }),
        ],
        [
          t("scheduler.last_started"),
          formatDate(state.schedulerStatus.last_started_at),
          t("scheduler.last_started_detail", { value: formatDate(state.schedulerStatus.last_finished_at) }),
        ],
        [
          t("scheduler.backfill"),
          formatBooleanLabel(state.schedulerStatus.run_backfill_now),
          t("scheduler.backfill_detail", { count: state.schedulerStatus.iteration_count }),
        ],
      ];
      elements.schedulerStats.innerHTML = stats
        .map(
          ([label, value, detail]) => `
            <article class="ops-stat-card">
              <span>${label}</span>
              <strong>${value}</strong>
              <p>${detail}</p>
            </article>
          `
        )
        .join("");
    }

    if (state.providerError) {
      elements.providerError.textContent = state.providerError;
      elements.providerError.classList.remove("hidden");
    } else {
      elements.providerError.textContent = "";
      elements.providerError.classList.add("hidden");
    }

    elements.providerVerifyButton.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerVerifyButton.textContent = state.providerVerifyBusy ? t("provider.verifying") : t("provider.verify");
    elements.providerSmokeQueryInput.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerSmokePeriodSelect.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerSmokeForceCheckbox.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerSmokeButton.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerSmokeButton.textContent = state.providerSmokeBusy ? t("provider.running_smoke") : t("provider.run_smoke");

    if (state.providerVerifyFeedback) {
      elements.providerVerifyFeedback.innerHTML = `
        <strong>${state.providerVerifyFeedback.summary}</strong>
      `;
      elements.providerVerifyFeedback.classList.remove("hidden");
    } else {
      elements.providerVerifyFeedback.textContent = "";
      elements.providerVerifyFeedback.classList.add("hidden");
    }

    if (state.providerSmokeResult) {
      elements.providerSmokeFeedback.innerHTML = `
        <strong>${state.providerSmokeResult.summary}</strong>
        <p class="availability-message">
          ${t("provider.smoke_feedback", {
            search_status: formatStatusLabel(state.providerSmokeResult.search.status),
            probe_mode: state.providerSmokeResult.probe_mode,
            force_search: formatBooleanLabel(state.providerSmokeResult.force_search),
          })}
        </p>
      `;
      elements.providerSmokeFeedback.classList.remove("hidden");
    } else {
      elements.providerSmokeFeedback.textContent = "";
      elements.providerSmokeFeedback.classList.add("hidden");
    }

    if (state.providerLoading && !state.providerStatus) {
      elements.providerSummary.innerHTML = t("provider.loading_summary");
      elements.providerGrid.innerHTML = "";
    } else if (!state.providerStatus) {
      elements.providerSummary.innerHTML = t("provider.unavailable_summary");
      elements.providerGrid.innerHTML = "";
    } else {
      elements.providerSummary.innerHTML = `
        <strong>${state.providerStatus.requested_mode}</strong>
        <span> -> ${state.providerStatus.resolved_provider}</span>
        <p class="availability-message">${state.providerStatus.summary}</p>
      `;
      const cards = [state.providerStatus.github, state.providerStatus.newsnow].map((check) => renderProviderCard(check));
      if (state.providerVerifyFeedback) {
        cards.push(renderProviderVerifyCard(state.providerVerifyFeedback.github));
        cards.push(renderProviderVerifyCard(state.providerVerifyFeedback.newsnow));
      }
      elements.providerGrid.innerHTML = cards.join("");
    }

    if (state.providerSmokeBusy && !state.providerSmokeResult) {
      elements.providerSmokeGrid.innerHTML = `
        <div class="empty-state">
          ${t("provider.running_smoke")}
        </div>
      `;
      elements.providerSmokeGrid.classList.remove("hidden");
    } else if (!state.providerSmokeResult) {
      elements.providerSmokeGrid.innerHTML = "";
      elements.providerSmokeGrid.classList.add("hidden");
    } else {
      elements.providerSmokeGrid.innerHTML = [
        renderProviderSmokeSearchCard(state.providerSmokeResult),
        renderProviderSmokeNextStepsCard(state.providerSmokeResult),
      ].join("");
      elements.providerSmokeGrid.classList.remove("hidden");
    }

    elements.collectTrackedButton.disabled = state.collectBusy;
    elements.collectQueryButton.disabled = state.collectBusy;
    elements.collectTrackedButton.textContent = state.collectBusy ? t("action.working") : t("collect.tracked");
    elements.collectQueryButton.textContent = state.collectBusy ? t("action.working") : t("collect.query");

    if (state.collectError) {
      elements.collectError.textContent = state.collectError;
      elements.collectError.classList.remove("hidden");
    } else {
      elements.collectError.textContent = "";
      elements.collectError.classList.add("hidden");
    }

    if (state.collectFeedback) {
      elements.collectFeedback.textContent = state.collectFeedback;
      elements.collectFeedback.classList.remove("hidden");
    } else {
      elements.collectFeedback.textContent = "";
      elements.collectFeedback.classList.add("hidden");
    }

    if (!state.collectResults.length) {
      elements.collectResults.innerHTML = "";
    } else {
      elements.collectResults.innerHTML = state.collectResults
        .map(
          (item) => `
            <article class="collect-result-item">
              <strong>${item.query}</strong>
              <div class="collect-result-meta">
                <span>${t("collect.keyword_ref", { id: item.keyword_id })}</span>
                <span>${t("collect.status", { value: formatStatusLabel(item.status) })}</span>
                <span>${item.tracked ? t("collect.tracked_state") : t("collect.untracked_state")}</span>
              </div>
            </article>
          `
        )
        .join("");
    }

    if (state.collectRunsError) {
      elements.runsError.textContent = state.collectRunsError;
      elements.runsError.classList.remove("hidden");
    } else {
      elements.runsError.textContent = "";
      elements.runsError.classList.add("hidden");
    }

    if (state.collectRunsLoading && !state.collectRuns.length) {
      elements.collectRuns.innerHTML = `
        <div class="empty-state">
          ${t("collect.loading_runs")}
        </div>
      `;
    } else if (!state.collectRuns.length) {
      elements.collectRuns.innerHTML = `
        <div class="empty-state">
          ${t("collect.no_runs")}
        </div>
      `;
    } else {
      elements.collectRuns.innerHTML = state.collectRuns
        .map(
          (run) => `
            <article class="ops-run-item">
              <strong>${translateToken("source", run.source)} / ${run.run_type}</strong>
              <div class="ops-run-meta">
                <span>${formatStatusLabel(run.status)}</span>
                <span>${formatDuration(run.duration_ms)}</span>
                <span>${formatDate(run.created_at)}</span>
                <span>${run.keyword_id ? t("collect.keyword_ref", { id: run.keyword_id }) : t("collect.global_run")}</span>
              </div>
              <p class="ops-run-message">${run.message || t("collect.no_message")}</p>
            </article>
          `
        )
        .join("");
    }
  }

  function renderRecentSearches() {
    if (!state.recentSearches.length) {
      elements.recentPanel.classList.add("hidden");
      elements.recentSearches.innerHTML = "";
      return;
    }

    elements.recentPanel.classList.remove("hidden");
    elements.recentSearches.innerHTML = state.recentSearches
      .map(
        (item, index) => `
          <button class="recent-chip" data-recent-index="${index}" type="button">
            <strong>${item.query}</strong>
            <span>${formatPeriodLabel(item.period)} · ${formatContentSourceLabel(item.contentSource)}</span>
          </button>
        `
      )
      .join("");
  }

  function renderTrend() {
    const visibleSeries = getVisibleSeries();

    elements.trendHeading.textContent = state.result
      ? state.result.keyword.kind === "github_repo"
        ? t("result.trend_title_repo")
        : t("result.trend_title_keyword")
      : t("heading.default");
    elements.trendSubtitle.textContent = state.result
      ? t("trend.subtitle", { period: formatPeriodLabel(state.period), count: visibleSeries.length })
      : "";

    const trendNote = getTrendNote();
    if (trendNote) {
      elements.trendNote.textContent = trendNote;
      elements.trendNote.classList.remove("hidden");
    } else {
      elements.trendNote.textContent = "";
      elements.trendNote.classList.add("hidden");
    }

    if (!state.result || !state.result.trend.series.length) {
      elements.seriesLegend.classList.add("hidden");
      elements.seriesLegend.innerHTML = "";
    } else {
      elements.seriesLegend.classList.remove("hidden");
      elements.seriesLegend.innerHTML = state.result.trend.series
        .map((series) => {
          const key = getSeriesKey(series);
          const hidden = state.hiddenSeriesKeys.includes(key) ? " is-hidden" : "";
          return `<button class="legend-chip${hidden}" data-series-key="${key}" type="button">${formatSeriesLabel(series)}</button>`;
        })
        .join("");
    }

    if (!visibleSeries.length) {
      elements.seriesGrid.innerHTML = `
        <div class="empty-state">
          ${t("trend.no_visible")}
        </div>
      `;
      return;
    }

    elements.seriesGrid.innerHTML = visibleSeries
      .map(
        (series) => `
          <article class="series-card">
            <header>
              <div>
                <h3>${formatSeriesLabel(series)}</h3>
                <p>${formatSourceTypeLabel(series.source_type)}</p>
              </div>
              <p>${t("trend.points", { count: series.points.length })}</p>
            </header>
            ${sparklineSvg(series.points)}
          </article>
        `
      )
      .join("");
  }

  function renderContent() {
    if (!state.result) {
      elements.contentList.innerHTML = "";
      return;
    }

    if (!state.result.content_items.length) {
      const sourceLabel = state.contentSource === "all" ? "" : `${formatContentSourceLabel(state.contentSource)} `;
      elements.contentList.innerHTML = `
        <div class="empty-state">
          ${t("content.no_items", { source: sourceLabel })}
        </div>
      `;
      return;
    }

    elements.contentList.innerHTML = state.result.content_items
      .map(
        (item) => `
          <article class="content-item">
            <div class="content-meta">
              <span>${translateToken("source", item.source)}</span>
              <span>${formatSourceTypeLabel(item.source_type)}</span>
              <span>${formatDate(item.published_at)}</span>
            </div>
            <h3>${item.url ? `<a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a>` : item.title}</h3>
            <p>${item.summary || t("content.no_summary")}</p>
          </article>
        `
      )
      .join("");
  }

  function renderSnapshot() {
    if (!state.result) {
      elements.snapshotCards.innerHTML = "";
      return;
    }

    const snapshotItems = [
      [t("snapshot.github_delta"), state.result.snapshot.github_star_today ?? t("generic.na")],
      [t("snapshot.newsnow_platforms"), state.result.snapshot.newsnow_platform_count ?? t("generic.na")],
      [t("snapshot.newsnow_items"), state.result.snapshot.newsnow_item_count ?? t("generic.na")],
      [t("snapshot.updated_at"), formatDate(state.result.snapshot.updated_at)],
    ];

    elements.snapshotCards.innerHTML = snapshotItems
      .map(
        ([label, value]) => `
          <div class="stat-card">
            <span>${label}</span>
            <strong>${value}</strong>
          </div>
        `
      )
      .join("");
  }

  function renderAvailability() {
    if (!state.result) {
      elements.availabilityList.innerHTML = "";
      return;
    }

    const taskDetails = [];
    if (state.result.backfill_job) {
      if (state.result.backfill_job.error_message) {
          taskDetails.push({
          label: t("availability.backfill_job"),
          status: formatStatusLabel(state.result.backfill_job.status),
          message: state.result.backfill_job.error_message,
        });
      }
      state.result.backfill_job.tasks.forEach((task) => {
        if (task.message || ["failed", "partial"].includes(task.status)) {
          taskDetails.push({
            label: formatTaskLabel(task),
            status: formatStatusLabel(task.status),
            message: task.message || t("availability.no_detail"),
          });
        }
      });
    }

    elements.availabilityList.innerHTML = Object.entries(state.result.availability)
      .map(
        ([key, value]) => `
          <div class="availability-item">
              <div class="availability-copy">
                <span>${formatAvailabilityLabel(key)}</span>
              </div>
              <span class="availability-state">${formatStatusLabel(value)}</span>
            </div>
          `
      )
      .concat(
        taskDetails.map(
          (detail) => `
            <div class="availability-item">
              <div class="availability-copy">
                <span>${detail.label}</span>
                <p class="availability-message">${detail.message}</p>
              </div>
              <span class="availability-state">${detail.status}</span>
            </div>
          `
        )
      )
      .join("");
  }

  function performRender() {
    syncLocaleChrome();
    syncControls();
    renderNavigation();
    renderRecentSearches();
    renderTrackedKeywords();
    renderOperations();
    const showGuidance = state.view === "search" && !state.result && !state.loading;
    elements.starterGrid.classList.toggle("hidden", !showGuidance);
    elements.heroSection.classList.toggle("hidden", !showGuidance);
    const showSecondaryGrid =
      state.view === "tracked" ||
      !elements.recentPanel.classList.contains("hidden") ||
      !elements.trackedPanel.classList.contains("hidden");
    elements.secondaryGrid.classList.toggle("hidden", !showSecondaryGrid);
    elements.searchButton.disabled = state.loading;
    elements.searchButton.textContent = state.loading ? t("search.searching") : t("search.submit");
    elements.trackButton.disabled = state.trackingBusy || !state.result;
    elements.trackButton.dataset.trackState = !state.result ? "unavailable" : state.result.keyword.is_tracked ? "tracked" : "untracked";
    elements.trackButton.textContent = state.trackingBusy
      ? t("action.save")
      : state.result && state.result.keyword.is_tracked
        ? t("tracked.untrack")
        : t("status.track");

    if (state.error) {
      elements.errorState.textContent = state.error;
      elements.errorState.classList.remove("hidden");
    } else {
      elements.errorState.textContent = "";
      elements.errorState.classList.add("hidden");
    }

    if (state.loading && !state.result) {
      elements.loadingPanel.classList.remove("hidden");
    } else {
      elements.loadingPanel.classList.add("hidden");
    }

    if (!state.result && !state.loading) {
      elements.emptyState.classList.add("hidden");
      elements.resultSummary.classList.add("hidden");
      elements.dashboard.classList.add("hidden");
      renderStatusRibbon();
      return;
    }

    elements.emptyState.classList.add("hidden");
    if (state.result) {
      renderResultSummary();
      elements.dashboard.classList.remove("hidden");
      renderStatusRibbon();
      renderTrend();
      renderContent();
      renderSnapshot();
      renderAvailability();
    } else {
      elements.resultSummary.classList.add("hidden");
    }
  }

  function render() {
    if (renderScheduled) {
      return;
    }
    renderScheduled = true;
    renderFrameHandle = window.requestAnimationFrame(function () {
      renderScheduled = false;
      renderFrameHandle = 0;
      performRender();
    });
  }

  function stopPolling() {
    if (state.pollTimer) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  async function saveTrackState(keywordId, tracked) {
    await request(`/api/keywords/${keywordId}/track`, {
      method: tracked ? "POST" : "DELETE",
    });
  }

  function syncCollectStateFromControls() {
    state.collectQuery = elements.collectQueryInput.value.trim();
    state.collectPeriod = elements.collectPeriodSelect.value;
    state.collectRunBackfillNow = elements.collectBackfillCheckbox.checked;
  }

  function syncProviderSmokeStateFromControls() {
    state.providerSmokeQuery = elements.providerSmokeQueryInput.value.trim();
    state.providerSmokePeriod = elements.providerSmokePeriodSelect.value;
    state.providerSmokeForceSearch = elements.providerSmokeForceCheckbox.checked;
  }

  async function triggerCollection(mode) {
    syncCollectStateFromControls();

    if (mode === "query" && !state.collectQuery) {
      state.collectError = t("collect.query_required");
      state.collectFeedback = null;
      state.collectResults = [];
      render();
      return;
    }

    state.collectBusy = true;
    state.collectError = null;
    state.collectFeedback = null;
    state.collectResults = [];
    render();

    try {
      const payload = {
        query: mode === "query" ? state.collectQuery : null,
        tracked_only: mode !== "query",
        period: state.collectPeriod,
        run_backfill_now: state.collectRunBackfillNow,
      };
      const response = await request("/api/collect/trigger", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.collectFeedback = t("collect.feedback", { count: response.triggered_count });
      state.collectResults = response.results;
      await Promise.all([loadTrackedKeywords(), loadOperationsData()]);
    } catch (error) {
      state.collectError = error instanceof Error ? error.message : t("collect.trigger_error");
    } finally {
      state.collectBusy = false;
      render();
    }
  }

  async function verifyProviders() {
    state.providerVerifyBusy = true;
    state.providerError = null;
    state.providerVerifyFeedback = null;
    render();

    try {
      state.providerVerifyFeedback = await request("/api/provider-verify", {
        method: "POST",
        body: JSON.stringify({ probe_mode: "real" }),
      });
      await loadOperationsData();
    } catch (error) {
      state.providerError = error instanceof Error ? error.message : t("provider.verify_error");
    } finally {
      state.providerVerifyBusy = false;
      render();
    }
  }

  async function runProviderSmoke() {
    syncProviderSmokeStateFromControls();
    if (!state.providerSmokeQuery) {
      state.providerSmokeQuery = elements.collectQueryInput.value.trim() || state.query || DEFAULT_PROVIDER_SMOKE_QUERY;
    }

    state.providerSmokeBusy = true;
    state.providerError = null;
    state.providerVerifyFeedback = null;
    state.providerSmokeResult = null;
    render();

    try {
      const payload = await request("/api/provider-smoke", {
        method: "POST",
        body: JSON.stringify({
          query: state.providerSmokeQuery,
          period: state.providerSmokePeriod,
          probe_mode: "real",
          force_search: state.providerSmokeForceSearch,
        }),
      });
      state.providerStatus = payload.provider_status;
      state.providerVerifyFeedback = payload.provider_verify;
      state.providerSmokeResult = payload;
      await loadOperationsData();
    } catch (error) {
      state.providerError = error instanceof Error ? error.message : t("provider.smoke_error");
    } finally {
      state.providerSmokeBusy = false;
      render();
    }
  }

  async function loadSearch() {
    if (!state.query) {
      state.result = null;
      state.error = null;
      state.loading = false;
      stopPolling();
      render();
      return;
    }

    state.loading = true;
    state.error = null;
    render();

    try {
      let payload = null;
      while (true) {
        const requestedPeriod = state.period;
        const params = new URLSearchParams({
          q: state.query,
          period: requestedPeriod,
          content_source: state.contentSource,
        });
        payload = await request(`/api/search?${params.toString()}`);
        if (shouldAutoExpandRepoHistory(payload, requestedPeriod)) {
          state.period = DEFAULT_REPO_PERIOD;
          syncControls();
          setUrlState();
          continue;
        }
        break;
      }

      state.result = payload;
      rememberRecentSearch(payload);
      state.hiddenSeriesKeys = state.hiddenSeriesKeys.filter((key) =>
        payload.trend.series.some((series) => getSeriesKey(series) === key)
      );
      state.error = null;
      render();
      schedulePolling();
    } catch (error) {
      state.error = error instanceof Error ? error.message : t("search.failed");
      state.result = null;
      stopPolling();
      render();
    } finally {
      state.loading = false;
      render();
    }
  }

  function schedulePolling() {
    stopPolling();
    if (!state.result || !state.result.backfill_job) {
      return;
    }
    if (!["pending", "running"].includes(state.result.backfill_job.status)) {
      return;
    }

    state.pollTimer = window.setInterval(async function () {
      if (!state.result) {
        stopPolling();
        return;
      }
      try {
        const status = await request(`/api/keywords/${state.result.keyword.id}/backfill-status`);
        state.result.backfill_job = {
          ...(state.result.backfill_job || { id: status.job_id, status: status.status, tasks: [] }),
          id: status.job_id,
          status: status.status,
          tasks: status.tasks,
        };

        const historyTask = status.tasks.find((task) => task.source === "github" && task.task_type === "history");
        const newsTask = status.tasks.find((task) => task.source === "newsnow");
        if (historyTask) {
          state.result.availability.github_history = historyTask.status === "success" ? "ready" : historyTask.status;
        }
        if (newsTask) {
          state.result.availability.newsnow_snapshot = newsTask.status === "success" ? "ready" : newsTask.status;
        }
        render();

        if (["success", "partial", "failed"].includes(status.status)) {
          stopPolling();
          await loadSearch();
        }
      } catch (_) {
        stopPolling();
      }
    }, 1200);
  }

  async function toggleTrack() {
    if (!state.result) {
      return;
    }

    state.trackingBusy = true;
    state.error = null;
    render();

    try {
      const tracked = !state.result.keyword.is_tracked;
      await saveTrackState(state.result.keyword.id, tracked);
      state.result.keyword.is_tracked = tracked;
      await loadTrackedKeywords();
    } catch (error) {
      state.error = error instanceof Error ? error.message : t("tracked.update_error");
    } finally {
      state.trackingBusy = false;
      render();
    }
  }

  async function untrackFromWatchlist(keywordId) {
    if (state.trackedBusyIds.includes(keywordId)) {
      return;
    }

    state.trackedBusyIds = state.trackedBusyIds.concat(keywordId);
    state.trackedError = null;
    render();

    try {
      await saveTrackState(keywordId, false);
      if (state.result && state.result.keyword.id === keywordId) {
        state.result.keyword.is_tracked = false;
      }
      await loadTrackedKeywords();
    } catch (error) {
      state.trackedError = error instanceof Error ? error.message : t("tracked.update_error");
    } finally {
      state.trackedBusyIds = state.trackedBusyIds.filter((id) => id !== keywordId);
      render();
    }
  }

  elements.searchForm.addEventListener("submit", function (event) {
    event.preventDefault();
    state.query = elements.queryInput.value.trim();
    if (!state.query) {
      render();
      return;
    }
    state.period = state.periodAuto ? getAutoPeriodForQuery(state.query) : elements.periodSelect.value;
    setUrlState();
    loadSearch();
  });

  elements.starterActions.addEventListener("click", function (event) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest("[data-starter-query]");
    if (!(button instanceof HTMLElement)) {
      return;
    }
    const starterQuery = button.dataset.starterQuery;
    if (!starterQuery) {
      return;
    }
    state.view = "search";
    state.query = starterQuery;
    state.period = button.dataset.starterPeriod || DEFAULT_PERIOD;
    state.periodAuto = false;
    state.contentSource = "all";
    syncControls();
    setUrlState();
    loadSearch();
  });

  elements.periodSelect.addEventListener("change", function () {
    state.period = elements.periodSelect.value;
    state.periodAuto = false;
  });

  elements.contentSourceSelect.addEventListener("change", function () {
    state.contentSource = elements.contentSourceSelect.value;
    setUrlState();
    if (state.query) {
      loadSearch();
    } else {
      render();
    }
  });

  elements.trackButton.addEventListener("click", function () {
    toggleTrack();
  });

  elements.langZhButton.addEventListener("click", function () {
    state.locale = "zh";
    persistLocale();
    render();
  });

  elements.langEnButton.addEventListener("click", function () {
    state.locale = "en";
    persistLocale();
    render();
  });

  elements.searchViewLink.addEventListener("click", function (event) {
    event.preventDefault();
    navigateToView("search");
  });

  elements.trackedViewLink.addEventListener("click", function (event) {
    event.preventDefault();
    navigateToView("tracked");
    Promise.all([loadTrackedKeywords(), loadOperationsData()]);
  });

  elements.operationsRefreshButton.addEventListener("click", function () {
    Promise.all([loadTrackedKeywords(), loadOperationsData()]);
  });

  elements.providerVerifyButton.addEventListener("click", function () {
    verifyProviders();
  });

  elements.providerSmokeForm.addEventListener("submit", function (event) {
    event.preventDefault();
    runProviderSmoke();
  });

  elements.collectForm.addEventListener("submit", function (event) {
    event.preventDefault();
    triggerCollection("tracked");
  });

  elements.collectQueryButton.addEventListener("click", function () {
    triggerCollection("query");
  });

  elements.recentSearches.addEventListener("click", function (event) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest("[data-recent-index]");
    if (!(button instanceof HTMLElement)) {
      return;
    }
    const recentIndex = Number(button.dataset.recentIndex);
    const entry = state.recentSearches[recentIndex];
    if (!entry) {
      return;
    }
    state.query = entry.query;
    state.period = entry.period;
    state.periodAuto = false;
    state.contentSource = entry.contentSource;
    syncControls();
    setUrlState();
    loadSearch();
  });

  elements.recentClearButton.addEventListener("click", function () {
    state.recentSearches = [];
    persistRecentSearches();
    render();
  });

  elements.trackedRefreshButton.addEventListener("click", function () {
    loadTrackedKeywords();
  });

  elements.trackedList.addEventListener("click", function (event) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const jumpButton = target.closest("[data-tracked-open-index]");
    if (jumpButton instanceof HTMLElement) {
      const trackedIndex = Number(jumpButton.dataset.trackedOpenIndex);
      const entry = state.trackedKeywords[trackedIndex];
      if (!entry) {
        return;
      }
      state.view = "search";
      state.query = getTrackedQuery(entry);
      state.period = getAutoPeriodForQuery(state.query, entry.kind);
      state.periodAuto = true;
      syncControls();
      setUrlState();
      loadSearch();
      return;
    }

    const toggleButton = target.closest("[data-tracked-id]");
    if (!(toggleButton instanceof HTMLElement)) {
      return;
    }
    const keywordId = Number(toggleButton.dataset.trackedId);
    if (!keywordId) {
      return;
    }
    untrackFromWatchlist(keywordId);
  });

  elements.seriesLegend.addEventListener("click", function (event) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest("[data-series-key]");
    if (!(button instanceof HTMLElement)) {
      return;
    }
    const seriesKey = button.dataset.seriesKey;
    if (!seriesKey) {
      return;
    }
    if (state.hiddenSeriesKeys.includes(seriesKey)) {
      state.hiddenSeriesKeys = state.hiddenSeriesKeys.filter((key) => key !== seriesKey);
    } else {
      state.hiddenSeriesKeys = state.hiddenSeriesKeys.concat(seriesKey);
    }
    render();
  });

  window.addEventListener("popstate", function () {
    parseLocationState();
    syncControls();
    render();
    loadTrackedKeywords();
    loadOperationsData();
    if (state.query) {
      loadSearch();
    } else {
      stopPolling();
    }
  });

  parseLocationState();
  state.locale = loadLocale();
  state.recentSearches = loadRecentSearches();
  syncControls();
  render();
  loadTrackedKeywords();
  loadOperationsData();
  if (state.query) {
    loadSearch();
  }
})();
