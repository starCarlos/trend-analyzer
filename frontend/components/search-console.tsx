"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  getBackfillStatus,
  searchKeyword,
  setTracked,
  type BackfillTask,
  type ContentSource,
  type SearchResponse,
} from "@/lib/api";
import { Sparkline } from "@/components/sparkline";

const PERIOD_OPTIONS = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "all", label: "All" },
];

const CONTENT_SOURCE_OPTIONS: Array<{ value: ContentSource; label: string }> = [
  { value: "all", label: "All sources" },
  { value: "newsnow", label: "NewsNow" },
  { value: "github", label: "GitHub" },
];

function formatDate(value?: string | null) {
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

function formatAvailabilityLabel(key: string) {
  return key.replaceAll("_", " ");
}

function getSeriesKey(series: SearchResponse["trend"]["series"][number]) {
  return `${series.source}-${series.metric}-${series.source_type}`;
}

function formatSeriesLabel(series: SearchResponse["trend"]["series"][number]) {
  const metric = series.metric === "hot_hit_count" ? "items" : series.metric.replaceAll("_", " ");
  return `${series.source} ${metric}`;
}

function TaskPills({ tasks }: { tasks: BackfillTask[] }) {
  if (!tasks.length) {
    return null;
  }

  return (
    <>
      {tasks.map((task) => (
        <span className="pill" key={`${task.source}-${task.task_type}`}>
          <strong>{task.source}</strong>
          <span>{task.task_type}</span>
          <span>{task.status}</span>
        </span>
      ))}
    </>
  );
}

export function SearchConsole() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const initialPeriod = searchParams.get("period") ?? "30d";
  const initialContentSource = (searchParams.get("content_source") as ContentSource | null) ?? "all";

  const [query, setQuery] = useState(initialQuery);
  const [period, setPeriod] = useState(initialPeriod);
  const [contentSource, setContentSource] = useState<ContentSource>(initialContentSource);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [hiddenSeriesKeys, setHiddenSeriesKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trackingBusy, setTrackingBusy] = useState(false);
  const [isRouting, startTransition] = useTransition();

  const activeQuery = searchParams.get("q") ?? "";
  const activePeriod = searchParams.get("period") ?? period;
  const activeContentSource = (searchParams.get("content_source") as ContentSource | null) ?? contentSource;

  useEffect(() => {
    setQuery(initialQuery);
    setPeriod(initialPeriod);
    setContentSource(initialContentSource);
  }, [initialContentSource, initialPeriod, initialQuery]);

  useEffect(() => {
    setHiddenSeriesKeys((current) => {
      if (!result) {
        return [];
      }

      const availableKeys = new Set(result.trend.series.map(getSeriesKey));
      return current.filter((key) => availableKeys.has(key));
    });
  }, [result]);

  useEffect(() => {
    let cancelled = false;

    if (!activeQuery) {
      setResult(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setError(null);

    searchKeyword(activeQuery, activePeriod, activeContentSource)
      .then((payload) => {
        if (!cancelled) {
          setResult(payload);
        }
      })
      .catch((requestError: Error) => {
        if (!cancelled) {
          setError(requestError.message);
          setResult(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeContentSource, activePeriod, activeQuery]);

  useEffect(() => {
    if (!result?.backfill_job || !result.keyword.id) {
      return undefined;
    }

    if (!["pending", "running"].includes(result.backfill_job.status)) {
      return undefined;
    }

    const timer = window.setInterval(async () => {
      try {
        const status = await getBackfillStatus(result.keyword.id);
        setResult((current) => {
          if (!current) {
            return current;
          }

          return {
            ...current,
            availability: {
              ...current.availability,
              github_history:
                status.tasks.find((task) => task.source === "github" && task.task_type === "history")?.status ??
                current.availability.github_history,
              newsnow_snapshot:
                status.tasks.find((task) => task.source === "newsnow")?.status ??
                current.availability.newsnow_snapshot,
            },
            backfill_job: {
              ...(current.backfill_job ?? { id: status.job_id, status: status.status, tasks: [] }),
              id: status.job_id,
              status: status.status,
              tasks: status.tasks,
            },
          };
        });

        if (status.status === "success" || status.status === "partial" || status.status === "failed") {
          const refreshed = await searchKeyword(activeQuery, activePeriod, activeContentSource);
          setResult(refreshed);
          window.clearInterval(timer);
        }
      } catch {
        window.clearInterval(timer);
      }
    }, 1200);

    return () => window.clearInterval(timer);
  }, [activeContentSource, activePeriod, activeQuery, result?.backfill_job, result?.keyword.id]);

  const hasResult = Boolean(result);
  const visibleSeries = useMemo(
    () => result?.trend.series.filter((series) => !hiddenSeriesKeys.includes(getSeriesKey(series))) ?? [],
    [hiddenSeriesKeys, result]
  );

  const heading = useMemo(() => {
    if (!result) {
      return "Search one repository or keyword.";
    }
    return result.keyword.kind === "github_repo" ? "Repository intelligence, first." : "Keyword snapshot, then accumulation.";
  }, [result]);

  const trendNote = useMemo(() => {
    if (!result || result.keyword.kind !== "keyword") {
      return null;
    }

    const newsnowSeries = result.trend.series.find((series) => series.source === "newsnow" && series.metric === "hot_hit_count");
    if (!newsnowSeries) {
      return "No local keyword history yet. The first NewsNow snapshot starts accumulation from today.";
    }
    if (newsnowSeries.points.length === 1) {
      return "Accumulation started today. One snapshot is available now, and later collections will extend the curve.";
    }
    return "Keyword trend is rendered as a locally accumulated NewsNow daily snapshot curve.";
  }, [result]);

  const toggleSeriesVisibility = (seriesKey: string) => {
    setHiddenSeriesKeys((current) =>
      current.includes(seriesKey) ? current.filter((key) => key !== seriesKey) : [...current, seriesKey]
    );
  };

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }

    startTransition(() => {
      const params = new URLSearchParams();
      params.set("q", query.trim());
      params.set("period", period);
      if (contentSource !== "all") {
        params.set("content_source", contentSource);
      }
      router.push(`/?${params.toString()}`);
    });
  };

  const onChangeContentSource = (nextSource: ContentSource) => {
    setContentSource(nextSource);
    if (!activeQuery) {
      return;
    }

    startTransition(() => {
      const params = new URLSearchParams();
      params.set("q", activeQuery);
      params.set("period", activePeriod);
      if (nextSource !== "all") {
        params.set("content_source", nextSource);
      }
      router.push(`/?${params.toString()}`);
    });
  };

  const onToggleTrack = async () => {
    if (!result) {
      return;
    }

    setTrackingBusy(true);
    setError(null);
    try {
      await setTracked(result.keyword.id, !result.keyword.is_tracked);
      setResult({
        ...result,
        keyword: {
          ...result.keyword,
          is_tracked: !result.keyword.is_tracked,
        },
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update tracking state.");
    } finally {
      setTrackingBusy(false);
    }
  };

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-card">
          <div className="hero-label">
            <span>TrendScope</span>
            <span>Editorial MVP</span>
          </div>
          <h1>Heat maps lie. Timelines don&apos;t.</h1>
          <p>
            Search a GitHub repository or a plain keyword, return the first useful answer quickly, and let the rest of
            the data backfill in public.
          </p>
        </div>
        <aside className="hero-card hero-aside">
          <h2>Current scope</h2>
          <ul>
            <li>GitHub history for repository queries</li>
            <li>NewsNow snapshot for both repositories and plain keywords</li>
            <li>Track state and async backfill status</li>
          </ul>
        </aside>
      </section>

      <form className="search-bar hero-card" onSubmit={onSubmit}>
        <input
          className="search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Try openai/openai-python or MCP"
        />
        <select className="period-select" value={period} onChange={(event) => setPeriod(event.target.value)}>
          {PERIOD_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <button className="button-primary" type="submit" disabled={isRouting || loading}>
          {loading || isRouting ? "Searching..." : "Search"}
        </button>
      </form>

      {error ? <div className="error-state">{error}</div> : null}

      {!hasResult && !loading ? (
        <div className="empty-state">
          Start with a direct GitHub path for the strongest first-run result. Plain keywords work too, but they only
          gain history after repeated collection.
        </div>
      ) : null}

      {loading && !result ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Loading search frame</h2>
              <p className="panel-subtitle">The first response should land before history finishes backfilling.</p>
            </div>
          </div>
          <div className="loading-grid">
            <div className="loading-bar" />
            <div className="loading-bar" />
            <div className="loading-bar" />
            <div className="loading-bar" />
          </div>
        </section>
      ) : null}

      {result ? (
        <>
          <div className="status-ribbon">
            <span className="pill">
              <strong>{result.keyword.normalized_query}</strong>
            </span>
            <span className="pill">
              <strong>kind</strong>
              <span>{result.keyword.kind}</span>
            </span>
            <span className="pill">
              <strong>track</strong>
              <span>{result.keyword.is_tracked ? "active" : "idle"}</span>
            </span>
            {result.backfill_job ? (
              <span className="pill">
                <strong>job</strong>
                <span>{result.backfill_job.status}</span>
              </span>
            ) : null}
            <TaskPills tasks={result.backfill_job?.tasks ?? []} />
          </div>

          <section className="dashboard">
            <div className="stack">
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2 className="panel-title">{heading}</h2>
                    <p className="panel-subtitle">
                      Period {activePeriod}. {visibleSeries.length} visible source
                      {visibleSeries.length === 1 ? "" : "s"}.
                    </p>
                    {trendNote ? <p className="trend-note">{trendNote}</p> : null}
                  </div>
                  <button className="button-ghost" type="button" onClick={onToggleTrack} disabled={trackingBusy}>
                    {trackingBusy ? "Saving..." : result.keyword.is_tracked ? "Untrack" : "Track"}
                  </button>
                </div>
                {result.trend.series.length ? (
                  <div className="series-legend">
                    {result.trend.series.map((series) => {
                      const seriesKey = getSeriesKey(series);
                      const isHidden = hiddenSeriesKeys.includes(seriesKey);
                      return (
                        <button
                          className={`legend-chip${isHidden ? " is-hidden" : ""}`}
                          key={seriesKey}
                          type="button"
                          onClick={() => toggleSeriesVisibility(seriesKey)}
                        >
                          {formatSeriesLabel(series)}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
                <div className="series-grid">
                  {visibleSeries.map((series) => (
                    <article className="series-card" key={`${series.source}-${series.metric}-${series.source_type}`}>
                      <header>
                        <div>
                          <h3>
                            {series.source} / {series.metric}
                          </h3>
                          <p>{series.source_type}</p>
                        </div>
                        <p>{series.points.length} points</p>
                      </header>
                      <Sparkline points={series.points} />
                    </article>
                  ))}
                  {!visibleSeries.length ? (
                    <div className="empty-state">
                      No visible trend line is ready yet. For plain keywords, today&apos;s snapshot starts accumulation and
                      later collections extend the curve.
                    </div>
                  ) : null}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2 className="panel-title">Context stream</h2>
                    <p className="panel-subtitle">Recent items associated with the current query.</p>
                  </div>
                  <select
                    className="period-select"
                    value={contentSource}
                    onChange={(event) => onChangeContentSource(event.target.value as ContentSource)}
                  >
                    {CONTENT_SOURCE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="content-list">
                  {result.content_items.map((item) => (
                    <article className="content-item" key={item.id}>
                      <div className="content-meta">
                        <span>{item.source}</span>
                        <span>{item.source_type}</span>
                        <span>{formatDate(item.published_at)}</span>
                      </div>
                      <h3>
                        {item.url ? (
                          <a href={item.url} target="_blank" rel="noreferrer">
                            {item.title}
                          </a>
                        ) : (
                          item.title
                        )}
                      </h3>
                      <p>{item.summary ?? "No summary available yet."}</p>
                    </article>
                  ))}
                  {!result.content_items.length ? (
                    <div className="empty-state">
                      No {contentSource === "all" ? "" : `${contentSource} `}content items yet. Collection will populate
                      this area when that source is available.
                    </div>
                  ) : null}
                </div>
              </section>
            </div>

            <div className="stack">
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2 className="panel-title">Today&apos;s readout</h2>
                    <p className="panel-subtitle">Simple source facts, no synthetic composite score.</p>
                  </div>
                </div>
                <div className="cards">
                  <div className="stat-card">
                    <span>GitHub star delta</span>
                    <strong>{result.snapshot.github_star_today ?? "N/A"}</strong>
                  </div>
                  <div className="stat-card">
                    <span>NewsNow platforms</span>
                    <strong>{result.snapshot.newsnow_platform_count ?? "N/A"}</strong>
                  </div>
                  <div className="stat-card">
                    <span>NewsNow items</span>
                    <strong>{result.snapshot.newsnow_item_count ?? "N/A"}</strong>
                  </div>
                  <div className="stat-card">
                    <span>Updated at</span>
                    <strong>{formatDate(result.snapshot.updated_at)}</strong>
                  </div>
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2 className="panel-title">Availability</h2>
                    <p className="panel-subtitle">The UI treats partial success as normal.</p>
                  </div>
                </div>
                <div className="availability-list">
                  {Object.entries(result.availability).map(([key, value]) => (
                    <div className="availability-item" key={key}>
                      <span>{formatAvailabilityLabel(key)}</span>
                      <span className="availability-state">{value}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
