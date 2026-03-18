(function () {
  const RECENT_SEARCHES_KEY = "trendscope.recent-searches.v1";
  const LOCALE_KEY = "trendscope.locale.v1";
  const MAX_RECENT_SEARCHES = 10;
  const DEFAULT_PROVIDER_SMOKE_QUERY = "openai/openai-python";
  const DEFAULT_LOCALE = "zh";
  const MESSAGES = {
    zh: {
      document: { title: "TrendScope" },
      nav: { search: "搜索", tracked: "追踪" },
      hero: {
        runtime: "Python 运行时",
        headline: "热榜会骗人，时间线不会。",
        description: "搜索 GitHub 仓库或普通关键词，先尽快返回第一批有用结果，再把剩余数据公开回填。",
        scope_title: "当前范围",
        scope_github: "GitHub 历史趋势，仅用于仓库类查询",
        scope_newsnow: "NewsNow 快照，覆盖仓库和普通关键词",
        scope_tracking: "追踪状态、来源筛选和异步回填状态",
      },
      search: {
        placeholder: "试试 openai/openai-python 或 MCP",
        submit: "搜索",
        searching: "搜索中...",
        failed: "搜索失败。",
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
        default: "优先使用 GitHub 直接路径开始，首次结果更强。普通关键词也能查，但历史需要反复采集后才会形成。",
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
        no_history: "还没有本地关键词历史。第一条 NewsNow 快照会从今天开始积累。",
        one_point: "积累从今天开始。当前已有 1 个快照点位，后续采集会继续延长曲线。",
        curve: "关键词趋势图基于本地累计的 NewsNow 日快照曲线。",
        history_one_point: "已按 NewsNow 内容发布时间回溯历史，但当前只有 1 个点位。",
        history_curve: "关键词热度线已按 NewsNow 内容发布时间回溯，后续采集会继续补齐。",
        no_visible: "当前还没有可见趋势线。普通关键词会优先按 NewsNow 内容发布时间回溯；如果拿不到足够时间信息，就从今日快照起步并继续补齐。",
        points: "{count} 个点位",
      },
      source: { github: "GitHub", newsnow: "NewsNow" },
      task_type: { history: "历史", content: "内容", snapshot: "快照" },
      source_type: {
        github_repo: "GitHub 仓库",
        keyword: "关键词",
        timeline: "内容时间线",
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
      nav: { search: "Search", tracked: "Tracked" },
      hero: {
        runtime: "Python Runtime",
        headline: "Heat maps lie. Timelines don't.",
        description: "Search a GitHub repository or a plain keyword, return the first useful answer quickly, and let the rest of the data backfill in public.",
        scope_title: "Current scope",
        scope_github: "GitHub history for repository queries",
        scope_newsnow: "NewsNow snapshot for repositories and plain keywords",
        scope_tracking: "Track state, content source filters, and async backfill status",
      },
      search: {
        placeholder: "Try openai/openai-python or MCP",
        submit: "Search",
        searching: "Searching...",
        failed: "Search failed.",
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
        default: "Start with a direct GitHub path for the strongest first-run result. Plain keywords work too, but they only gain history after repeated collection.",
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
        no_history: "No local keyword history yet. The first NewsNow snapshot starts accumulation from today.",
        one_point: "Accumulation started today. One snapshot is available now, and later collections will extend the curve.",
        curve: "Keyword trend is rendered as a locally accumulated NewsNow daily snapshot curve.",
        history_one_point: "A first historical point was derived from NewsNow publish times, but only one point is available so far.",
        history_curve: "Keyword heat is backfilled from NewsNow publish times, and later collections will keep extending the line.",
        no_visible: "No visible trend line is ready yet. Plain keywords first try to backfill from NewsNow publish times; if that is too sparse, the curve starts from today's snapshot and grows over time.",
        points: "{count} points",
      },
      source: { github: "GitHub", newsnow: "NewsNow" },
      task_type: { history: "history", content: "content", snapshot: "snapshot" },
      source_type: {
        github_repo: "GitHub repo",
        keyword: "Keyword",
        timeline: "Content timeline",
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

  const elements = {
    searchViewLink: document.querySelector('[data-view-link="search"]'),
    trackedViewLink: document.querySelector('[data-view-link="tracked"]'),
    langZhButton: document.getElementById("lang-zh-button"),
    langEnButton: document.getElementById("lang-en-button"),
    dashboard: document.getElementById("dashboard"),
    emptyState: document.getElementById("empty-state"),
    errorState: document.getElementById("error-state"),
    loadingPanel: document.getElementById("loading-panel"),
    queryInput: document.getElementById("query-input"),
    periodSelect: document.getElementById("period-select"),
    contentSourceSelect: document.getElementById("content-source-select"),
    searchButton: document.getElementById("search-button"),
    searchForm: document.getElementById("search-form"),
    recentPanel: document.getElementById("recent-panel"),
    recentSearches: document.getElementById("recent-searches"),
    recentClearButton: document.getElementById("recent-clear-button"),
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
    state.period = params.get("period") || "30d";
    state.contentSource = params.get("content_source") || "all";
  }

  function syncControls() {
    elements.queryInput.value = state.query;
    elements.periodSelect.value = state.period;
    elements.contentSourceSelect.value = state.contentSource;
    elements.collectQueryInput.value = state.collectQuery;
    elements.collectPeriodSelect.value = state.collectPeriod;
    elements.collectBackfillCheckbox.checked = state.collectRunBackfillNow;
    elements.providerSmokeQueryInput.value = state.providerSmokeQuery;
    elements.providerSmokePeriodSelect.value = state.providerSmokePeriod;
    elements.providerSmokeForceCheckbox.checked = state.providerSmokeForceSearch;
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

  function getTrendNote() {
    if (!state.result || state.result.keyword.kind !== "keyword") {
      return null;
    }
    const historySeries = state.result.trend.series.find(
      (series) => series.source === "newsnow" && series.metric === "matched_item_count"
    );
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

  function renderStatusRibbon() {
    if (!state.result) {
      elements.statusRibbon.classList.add("hidden");
      elements.statusRibbon.innerHTML = "";
      return;
    }

    const pills = [];
    pills.push(`<span class="pill"><strong>${state.result.keyword.normalized_query}</strong></span>`);
    pills.push(`<span class="pill"><strong>${t("status.kind")}</strong><span>${translateToken("kind", state.result.keyword.kind)}</span></span>`);
    pills.push(
      `<span class="pill"><strong>${t("status.track")}</strong><span>${state.result.keyword.is_tracked ? t("status.tracked") : t("status.idle")}</span></span>`
    );
    if (state.result.backfill_job) {
      pills.push(`<span class="pill"><strong>${t("status.job")}</strong><span>${formatStatusLabel(state.result.backfill_job.status)}</span></span>`);
      state.result.backfill_job.tasks.forEach((task) => {
        pills.push(
          `<span class="pill"><strong>${translateToken("source", task.source)}</strong><span>${translateToken("task_type", task.task_type)}</span><span>${formatStatusLabel(task.status)}</span></span>`
        );
      });
    }

    elements.statusRibbon.innerHTML = pills.join("");
    elements.statusRibbon.classList.remove("hidden");
  }

  function renderTrackedKeywords() {
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

    elements.trendHeading.textContent = getHeading();
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

  function render() {
    syncLocaleChrome();
    syncControls();
    renderNavigation();
    renderRecentSearches();
    renderTrackedKeywords();
    renderOperations();
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
      elements.emptyState.classList.remove("hidden");
      elements.dashboard.classList.add("hidden");
      renderStatusRibbon();
      return;
    }

    elements.emptyState.classList.add("hidden");
    if (state.result) {
      elements.dashboard.classList.remove("hidden");
      renderStatusRibbon();
      renderTrend();
      renderContent();
      renderSnapshot();
      renderAvailability();
    }
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
      const params = new URLSearchParams({
        q: state.query,
        period: state.period,
        content_source: state.contentSource,
      });
      const payload = await request(`/api/search?${params.toString()}`);
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
    state.period = elements.periodSelect.value;
    setUrlState();
    loadSearch();
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
    state.contentSource = entry.contentSource;
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
