(function () {
  const RECENT_SEARCHES_KEY = "trendscope.recent-searches.v1";
  const MAX_RECENT_SEARCHES = 10;
  const DEFAULT_PROVIDER_SMOKE_QUERY = "openai/openai-python";

  const state = {
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
    return kind === "github_repo" ? "GitHub repo" : "Keyword";
  }

  async function loadTrackedKeywords() {
    state.trackedLoading = true;
    state.trackedError = null;
    render();

    try {
      state.trackedKeywords = await request("/api/keywords?tracked_only=true");
    } catch (error) {
      state.trackedError = error instanceof Error ? error.message : "Failed to load tracked keywords.";
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
        schedulerResult.reason instanceof Error ? schedulerResult.reason.message : "Failed to load scheduler status.";
    }

    if (runsResult.status === "fulfilled") {
      state.collectRuns = runsResult.value;
    } else {
      state.collectRuns = [];
      state.collectRunsError = runsResult.reason instanceof Error ? runsResult.reason.message : "Failed to load collect runs.";
    }

    if (providerResult.status === "fulfilled") {
      state.providerStatus = providerResult.value;
    } else {
      state.providerStatus = null;
      state.providerError = providerResult.reason instanceof Error ? providerResult.reason.message : "Failed to load provider status.";
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
      return "N/A";
    }
    return new Date(value).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatDuration(value) {
    if (value === null || value === undefined) {
      return "N/A";
    }
    return `${value} ms`;
  }

  function formatAvailabilityLabel(key) {
    return key.replaceAll("_", " ");
  }

  function formatTaskLabel(task) {
    return `${task.source} ${task.task_type}`;
  }

  function renderProviderCard(check) {
    const issuesMarkup = check.issues.length
      ? `
          <div class="provider-issues">
            <strong>Issues</strong>
            <ul class="provider-list">
              ${check.issues.map((item) => `<li>${item}</li>`).join("")}
            </ul>
          </div>
        `
      : "";
    const notesMarkup = check.notes.length
      ? `
          <div class="provider-notes">
            <strong>Notes</strong>
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
            <h3>${check.source}</h3>
            <p>${check.preferred_provider}${check.fallback_provider ? ` -> ${check.fallback_provider}` : ""}</p>
          </div>
          <span class="provider-chip">${check.status}</span>
        </header>
        <div class="provider-meta">
          <span>mode ${check.mode}</span>
          <span>real configured ${check.can_use_real_provider ? "true" : "false"}</span>
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
            <h3>${result.source}</h3>
            <p>${result.attempted_provider}</p>
          </div>
          <span class="provider-chip">${result.status}</span>
        </header>
        <div class="provider-meta">
          <span>${result.endpoint || "no endpoint"}</span>
        </div>
        <div class="provider-notes">
          <strong>Probe</strong>
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
      result.search.keyword_kind ? `keyword kind ${result.search.keyword_kind}` : null,
      result.search.normalized_query ? `normalized ${result.search.normalized_query}` : null,
      `trend series ${result.search.trend_series_count}`,
      `content items ${result.search.content_item_count}`,
      result.search.backfill_status ? `backfill ${result.search.backfill_status}` : null,
    ].filter(Boolean);
    const availabilityMarkup = availabilityEntries.length
      ? `
          <div class="provider-notes">
            <strong>Availability</strong>
            <ul class="provider-list">
              ${availabilityEntries.map(([key, value]) => `<li>${formatAvailabilityLabel(key)}: ${value}</li>`).join("")}
            </ul>
          </div>
        `
      : "";

    return `
      <article class="provider-card provider-smoke-card">
        <header>
          <div>
            <h3>Smoke search</h3>
            <p>${result.query} · ${result.period}</p>
          </div>
          <span class="provider-chip">${result.search.status}</span>
        </header>
        <div class="provider-meta">
          <span>probe ${result.probe_mode}</span>
          <span>force_search ${result.force_search ? "true" : "false"}</span>
        </div>
        <div class="provider-notes">
          <strong>Search</strong>
          <ul class="provider-list">
            ${details.map((item) => `<li>${item}</li>`).join("")}
          </ul>
        </div>
        ${availabilityMarkup}
      </article>
    `;
  }

  function renderProviderSmokeNextStepsCard(result) {
    const nextSteps = result.next_steps.length ? result.next_steps : ["当前 smoke 输出没有额外动作项。"];

    return `
      <article class="provider-card provider-smoke-card">
        <header>
          <div>
            <h3>Smoke next steps</h3>
            <p>Operator checklist from the backend smoke runner.</p>
          </div>
          <span class="provider-chip">guide</span>
        </header>
        <div class="provider-notes">
          <strong>Next steps</strong>
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
    const metric = series.metric === "hot_hit_count" ? "items" : series.metric.replaceAll("_", " ");
    return `${series.source} ${metric}`;
  }

  function getVisibleSeries() {
    if (!state.result) {
      return [];
    }
    return state.result.trend.series.filter((series) => !state.hiddenSeriesKeys.includes(getSeriesKey(series)));
  }

  function getHeading() {
    if (!state.result) {
      return "Search one repository or keyword.";
    }
    return state.result.keyword.kind === "github_repo"
      ? "Repository intelligence, first."
      : "Keyword snapshot, then accumulation.";
  }

  function getTrendNote() {
    if (!state.result || state.result.keyword.kind !== "keyword") {
      return null;
    }
    const newsnowSeries = state.result.trend.series.find(
      (series) => series.source === "newsnow" && series.metric === "hot_hit_count"
    );
    if (!newsnowSeries) {
      return "No local keyword history yet. The first NewsNow snapshot starts accumulation from today.";
    }
    if (newsnowSeries.points.length === 1) {
      return "Accumulation started today. One snapshot is available now, and later collections will extend the curve.";
    }
    return "Keyword trend is rendered as a locally accumulated NewsNow daily snapshot curve.";
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
  }

  function renderStatusRibbon() {
    if (!state.result) {
      elements.statusRibbon.classList.add("hidden");
      elements.statusRibbon.innerHTML = "";
      return;
    }

    const pills = [];
    pills.push(`<span class="pill"><strong>${state.result.keyword.normalized_query}</strong></span>`);
    pills.push(`<span class="pill"><strong>kind</strong><span>${state.result.keyword.kind}</span></span>`);
    pills.push(`<span class="pill"><strong>track</strong><span>${state.result.keyword.is_tracked ? "active" : "idle"}</span></span>`);
    if (state.result.backfill_job) {
      pills.push(`<span class="pill"><strong>job</strong><span>${state.result.backfill_job.status}</span></span>`);
      state.result.backfill_job.tasks.forEach((task) => {
        pills.push(
          `<span class="pill"><strong>${task.source}</strong><span>${task.task_type}</span><span>${task.status}</span></span>`
        );
      });
    }

    elements.statusRibbon.innerHTML = pills.join("");
    elements.statusRibbon.classList.remove("hidden");
  }

  function renderTrackedKeywords() {
    elements.trackedRefreshButton.disabled = state.trackedLoading || state.trackedBusyIds.length > 0;
    elements.trackedRefreshButton.textContent = state.trackedLoading ? "Refreshing..." : "Refresh";

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
          Loading tracked keywords from the local database.
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
                <span>updated ${formatDate(item.updated_at)}</span>
              </div>
            </div>
            <button class="button-ghost" data-tracked-id="${item.id}" type="button" ${busy ? "disabled" : ""}>
              ${busy ? "Saving..." : "Untrack"}
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
      ? "Refreshing..."
      : operationsBusy
        ? "Working..."
        : "Refresh";

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
          Loading scheduler snapshot from the backend.
        </div>
      `;
    } else if (!state.schedulerStatus) {
      elements.schedulerStats.innerHTML = `
        <div class="empty-state">
          Scheduler snapshot is not available yet.
        </div>
      `;
    } else {
      const stats = [
        ["Enabled", state.schedulerStatus.enabled ? "true" : "false", "Controlled by SCHEDULER_ENABLED."],
        ["Worker", state.schedulerStatus.running ? "running" : "idle", `Period ${state.schedulerStatus.period}.`],
        [
          "Interval",
          `${state.schedulerStatus.interval_seconds}s`,
          `Initial delay ${state.schedulerStatus.initial_delay_seconds}s.`,
        ],
        [
          "Last status",
          state.schedulerStatus.last_status,
          state.schedulerStatus.last_error || `Triggered ${state.schedulerStatus.last_triggered_count} keyword(s) last time.`,
        ],
        [
          "Last started",
          formatDate(state.schedulerStatus.last_started_at),
          `Last finished ${formatDate(state.schedulerStatus.last_finished_at)}.`,
        ],
        [
          "Backfill",
          state.schedulerStatus.run_backfill_now ? "true" : "false",
          `Iterations ${state.schedulerStatus.iteration_count}.`,
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
    elements.providerVerifyButton.textContent = state.providerVerifyBusy ? "Verifying..." : "Verify real";
    elements.providerSmokeQueryInput.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerSmokePeriodSelect.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerSmokeForceCheckbox.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerSmokeButton.disabled = state.providerVerifyBusy || state.providerSmokeBusy;
    elements.providerSmokeButton.textContent = state.providerSmokeBusy ? "Running..." : "Run smoke";

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
          Search ${state.providerSmokeResult.search.status}. Probe ${state.providerSmokeResult.probe_mode}. force_search
          ${state.providerSmokeResult.force_search ? "true" : "false"}.
        </p>
      `;
      elements.providerSmokeFeedback.classList.remove("hidden");
    } else {
      elements.providerSmokeFeedback.textContent = "";
      elements.providerSmokeFeedback.classList.add("hidden");
    }

    if (state.providerLoading && !state.providerStatus) {
      elements.providerSummary.innerHTML = "Loading provider preflight from the backend.";
      elements.providerGrid.innerHTML = "";
    } else if (!state.providerStatus) {
      elements.providerSummary.innerHTML = "Provider preflight is not available yet.";
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
          Running provider smoke with the backend and waiting for the end-to-end summary.
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
    elements.collectTrackedButton.textContent = state.collectBusy ? "Working..." : "Collect tracked";
    elements.collectQueryButton.textContent = state.collectBusy ? "Working..." : "Collect query";

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
                <span>keyword #${item.keyword_id}</span>
                <span>status ${item.status}</span>
                <span>${item.tracked ? "tracked" : "not tracked"}</span>
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
          Loading recent collect runs.
        </div>
      `;
    } else if (!state.collectRuns.length) {
      elements.collectRuns.innerHTML = `
        <div class="empty-state">
          No collect runs recorded yet.
        </div>
      `;
    } else {
      elements.collectRuns.innerHTML = state.collectRuns
        .map(
          (run) => `
            <article class="ops-run-item">
              <strong>${run.source} / ${run.run_type}</strong>
              <div class="ops-run-meta">
                <span>${run.status}</span>
                <span>${formatDuration(run.duration_ms)}</span>
                <span>${formatDate(run.created_at)}</span>
                <span>${run.keyword_id ? `keyword #${run.keyword_id}` : "global run"}</span>
              </div>
              <p class="ops-run-message">${run.message || "No extra message recorded."}</p>
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
            <span>${item.period} · ${item.contentSource}</span>
          </button>
        `
      )
      .join("");
  }

  function renderTrend() {
    const visibleSeries = getVisibleSeries();

    elements.trendHeading.textContent = getHeading();
    elements.trendSubtitle.textContent = state.result
      ? `Period ${state.period}. ${visibleSeries.length} visible source${visibleSeries.length === 1 ? "" : "s"}.`
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
          No visible trend line is ready yet. For plain keywords, today's snapshot starts accumulation and later
          collections extend the curve.
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
                <h3>${series.source} / ${series.metric}</h3>
                <p>${series.source_type}</p>
              </div>
              <p>${series.points.length} points</p>
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
      const sourceLabel = state.contentSource === "all" ? "" : `${state.contentSource} `;
      elements.contentList.innerHTML = `
        <div class="empty-state">
          No ${sourceLabel}content items yet. Collection will populate this area when that source is available.
        </div>
      `;
      return;
    }

    elements.contentList.innerHTML = state.result.content_items
      .map(
        (item) => `
          <article class="content-item">
            <div class="content-meta">
              <span>${item.source}</span>
              <span>${item.source_type}</span>
              <span>${formatDate(item.published_at)}</span>
            </div>
            <h3>${item.url ? `<a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a>` : item.title}</h3>
            <p>${item.summary || "No summary available yet."}</p>
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
      ["GitHub star delta", state.result.snapshot.github_star_today ?? "N/A"],
      ["NewsNow platforms", state.result.snapshot.newsnow_platform_count ?? "N/A"],
      ["NewsNow items", state.result.snapshot.newsnow_item_count ?? "N/A"],
      ["Updated at", formatDate(state.result.snapshot.updated_at)],
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
          label: "backfill job",
          status: state.result.backfill_job.status,
          message: state.result.backfill_job.error_message,
        });
      }
      state.result.backfill_job.tasks.forEach((task) => {
        if (task.message || ["failed", "partial"].includes(task.status)) {
          taskDetails.push({
            label: formatTaskLabel(task),
            status: task.status,
            message: task.message || "No additional detail provided.",
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
            <span class="availability-state">${value}</span>
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
    syncControls();
    renderNavigation();
    renderRecentSearches();
    renderTrackedKeywords();
    renderOperations();
    elements.searchButton.disabled = state.loading;
    elements.searchButton.textContent = state.loading ? "Searching..." : "Search";
    elements.trackButton.disabled = state.trackingBusy || !state.result;
    elements.trackButton.textContent = state.trackingBusy
      ? "Saving..."
      : state.result && state.result.keyword.is_tracked
        ? "Untrack"
        : "Track";

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
      state.collectError = "Enter a query before running one-off collection.";
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
      state.collectFeedback = `Triggered ${response.triggered_count} collection run(s).`;
      state.collectResults = response.results;
      await Promise.all([loadTrackedKeywords(), loadOperationsData()]);
    } catch (error) {
      state.collectError = error instanceof Error ? error.message : "Failed to trigger collection.";
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
      state.providerError = error instanceof Error ? error.message : "Failed to verify provider connectivity.";
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
      state.providerError = error instanceof Error ? error.message : "Failed to run provider smoke.";
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
      state.error = error instanceof Error ? error.message : "Search failed.";
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
      state.error = error instanceof Error ? error.message : "Failed to update tracking state.";
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
      state.trackedError = error instanceof Error ? error.message : "Failed to update tracked keyword.";
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
  state.recentSearches = loadRecentSearches();
  syncControls();
  render();
  loadTrackedKeywords();
  loadOperationsData();
  if (state.query) {
    loadSearch();
  }
})();
