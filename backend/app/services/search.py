import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from itertools import groupby

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models import BackfillJob, BackfillJobTask, ContentItem, Keyword, TrendPoint, utcnow
from app.config import get_settings
from app.schemas import (
    BackfillJobPayload,
    BackfillStatusPayload,
    BackfillTaskPayload,
    ContentItemPayload,
    KeywordPayload,
    SearchResponsePayload,
    SnapshotPayload,
    TrendPayload,
    TrendPeriodPayload,
    TrendPointPayload,
    TrendSeriesPayload,
)
from app.services.github_repo_resolution import resolve_github_repo_name
from app.services.backfill import (
    KEYWORD_HISTORY_SOURCES,
    _derive_keyword_history_points,
    _upsert_content_item,
    _upsert_trend_point,
    run_backfill_job,
)
from app.services.archive_relevance import (
    archive_match_strength,
    build_ambiguous_query_contexts,
    gdelt_matches_query,
    gdelt_title_key,
    gdelt_title_token_set,
    token_jaccard,
)
from app.services.providers import get_data_provider
from app.services.provider_registry import ARCHIVE_PROVIDER_FETCHERS
from app.services.provider_types import TrendPointInput
from app.services.query_parser import SearchTarget, resolve_search_query


ALLOWED_PERIODS = {"7d": 7, "30d": 30, "90d": 90, "all": None}
ALLOWED_CONTENT_SOURCES = {"all", "github", "newsnow", "google_news", "direct_rss", "gdelt"}
ARCHIVE_CONTENT_SOURCES = ("google_news", "direct_rss", "gdelt")
CONTENT_REFRESH_WINDOW = timedelta(minutes=30)
ARCHIVE_SOURCE_PRIORITY = {"direct_rss": 0, "google_news": 1, "gdelt": 2}


def parse_period(period: str) -> int | None:
    if period not in ALLOWED_PERIODS:
        raise HTTPException(status_code=400, detail="period must be one of 7d, 30d, 90d, all")
    return ALLOWED_PERIODS[period]


def parse_content_source(content_source: str) -> str | None:
    if content_source not in ALLOWED_CONTENT_SOURCES:
        raise HTTPException(
            status_code=400,
            detail="content_source must be one of all, github, newsnow, google_news, direct_rss, gdelt",
        )
    return None if content_source == "all" else content_source


def get_or_create_keyword(db: Session, target: SearchTarget) -> Keyword:
    keyword = db.scalar(
        select(Keyword).where(
            Keyword.normalized_query == target.normalized_query,
            Keyword.kind == target.kind,
        )
    )
    if keyword:
        keyword.raw_query = target.raw_query
        keyword.updated_at = utcnow()
        db.commit()
        db.refresh(keyword)
        return keyword

    keyword = Keyword(
        raw_query=target.raw_query,
        normalized_query=target.normalized_query,
        kind=target.kind,
        target_ref=target.target_ref,
    )
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    return keyword


def _latest_job(db: Session, keyword_id: int) -> BackfillJob | None:
    return db.scalar(
        select(BackfillJob)
        .options(selectinload(BackfillJob.tasks))
        .where(BackfillJob.keyword_id == keyword_id)
        .order_by(desc(BackfillJob.requested_at))
    )


def _has_github_history(db: Session, keyword_id: int) -> bool:
    return (
        db.scalar(
            select(TrendPoint.id).where(
                TrendPoint.keyword_id == keyword_id,
                TrendPoint.source == "github",
                TrendPoint.metric == "star_delta",
            )
        )
        is not None
    )


def _has_keyword_history(db: Session, keyword_id: int) -> bool:
    return (
        db.scalar(
            select(TrendPoint.id).where(
                TrendPoint.keyword_id == keyword_id,
                TrendPoint.metric == "matched_item_count",
                TrendPoint.source_type == "timeline",
            )
        )
        is not None
    )


def _has_fresh_newsnow_snapshot(db: Session, keyword_id: int) -> bool:
    point = db.scalar(
        select(TrendPoint)
        .where(
            TrendPoint.keyword_id == keyword_id,
            TrendPoint.source == "newsnow",
        )
        .order_by(desc(TrendPoint.collected_at))
    )
    if not point:
        return False
    return point.collected_at >= utcnow() - CONTENT_REFRESH_WINDOW


def _has_fresh_content_items(db: Session, keyword_id: int, source: str) -> bool:
    item = db.scalar(
        select(ContentItem)
        .where(
            ContentItem.keyword_id == keyword_id,
            ContentItem.source == source,
        )
        .order_by(desc(ContentItem.fetched_at))
    )
    if not item:
        return False
    return item.fetched_at >= utcnow() - CONTENT_REFRESH_WINDOW


def _has_keyword_history_content(db: Session, keyword_id: int) -> bool:
    return (
        db.scalar(
            select(ContentItem.id).where(
                ContentItem.keyword_id == keyword_id,
                ContentItem.source.in_(tuple(sorted(KEYWORD_HISTORY_SOURCES))),
                ContentItem.published_at.is_not(None),
            )
        )
        is not None
    )


def _has_archive_timeline(db: Session, keyword_id: int, source: str) -> bool:
    return (
        db.scalar(
            select(TrendPoint.id).where(
                TrendPoint.keyword_id == keyword_id,
                TrendPoint.source == source,
                TrendPoint.metric == "matched_item_count",
                TrendPoint.source_type == "timeline",
            )
        )
        is not None
    )


def _archive_queries(keyword: Keyword) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None) -> None:
        if not candidate:
            return
        normalized = " ".join(candidate.split()).strip().strip("/")
        if not normalized:
            return
        identity = normalized.casefold()
        if identity in seen:
            return
        seen.add(identity)
        queries.append(normalized)

    if keyword.kind == "keyword":
        add(keyword.normalized_query)
        return queries

    raw_query = keyword.raw_query.strip()
    if raw_query and "/" not in raw_query and not raw_query.startswith(("http://", "https://")):
        add(raw_query)

    repo_name = (keyword.target_ref or keyword.normalized_query).rsplit("/", 1)[-1]
    add(repo_name)
    return queries


def _derive_archive_timeline_points(db: Session, keyword: Keyword, source: str) -> list[TrendPointInput]:
    content_items = list(
        db.scalars(
            select(ContentItem)
            .where(
                ContentItem.keyword_id == keyword.id,
                ContentItem.source == source,
                ContentItem.published_at.is_not(None),
            )
            .order_by(ContentItem.published_at.asc(), ContentItem.id.asc())
        )
    )

    counts_by_day: dict = {}
    for item in content_items:
        if not item.published_at:
            continue
        bucket_start = item.published_at.replace(hour=0, minute=0, second=0, microsecond=0)
        counts_by_day[bucket_start] = counts_by_day.get(bucket_start, 0) + 1

    if not counts_by_day:
        return []

    raw_json = json.dumps(
        {
            "query": keyword.normalized_query,
            "derived_from": f"{source}_archive",
            "content_item_count": len(content_items),
            "bucket_count": len(counts_by_day),
        }
    )

    return [
        TrendPointInput(
            source=source,
            metric="matched_item_count",
            source_type="timeline",
            bucket_granularity="day",
            bucket_start=bucket_start,
            value=float(count),
            raw_json=raw_json,
        )
        for bucket_start, count in sorted(counts_by_day.items())
    ]


def _prefetch_content_history_inline(db: Session, keyword: Keyword) -> bool:
    if keyword.kind not in {"keyword", "github_repo"}:
        return False

    changed = False
    has_history = _has_keyword_history(db, keyword.id)
    has_history_content = _has_keyword_history_content(db, keyword.id)
    has_archive_timelines = {
        source: _has_archive_timeline(db, keyword.id, source)
        for source in ARCHIVE_CONTENT_SOURCES
    }

    if keyword.kind == "keyword" and has_history_content and not has_history:
        for point in _derive_keyword_history_points(db, keyword):
            _upsert_trend_point(db, keyword.id, point)
        db.commit()
        return True

    provider = get_data_provider()
    for source, fetcher_name in ARCHIVE_PROVIDER_FETCHERS:
        if _has_fresh_content_items(db, keyword.id, source):
            continue
        archive_fetcher = getattr(provider, fetcher_name, None)
        if not callable(archive_fetcher):
            continue

        archive_items = []
        for archive_query in _archive_queries(keyword):
            try:
                archive_items = archive_fetcher(archive_query)
            except Exception:
                db.rollback()
                archive_items = []
                continue
            if archive_items:
                break

        if archive_items:
            for item in archive_items:
                _upsert_content_item(db, keyword.id, item)
            db.flush()
            changed = True
            has_history_content = True

    if has_history_content and (changed or not has_history):
        for point in _derive_keyword_history_points(db, keyword):
            _upsert_trend_point(db, keyword.id, point)
        changed = True

    if keyword.kind == "keyword" and not has_history_content and not _has_fresh_newsnow_snapshot(db, keyword.id):
        try:
            snapshot_points, snapshot_items = provider.fetch_newsnow_snapshot(keyword.normalized_query)
        except Exception:
            db.rollback()
        else:
            for point in snapshot_points:
                _upsert_trend_point(db, keyword.id, point)
            for item in snapshot_items:
                _upsert_content_item(db, keyword.id, item)
            db.flush()
            changed = True
            has_history_content = any(item.published_at for item in snapshot_items)
            if has_history_content:
                for point in _derive_keyword_history_points(db, keyword):
                    _upsert_trend_point(db, keyword.id, point)
                changed = True

    if keyword.kind == "github_repo":
        for source in ARCHIVE_CONTENT_SOURCES:
            archive_timeline = _derive_archive_timeline_points(db, keyword, source)
            if archive_timeline and (changed or not has_archive_timelines[source]):
                for point in archive_timeline:
                    _upsert_trend_point(db, keyword.id, point)
                changed = True

    if changed:
        db.commit()
        return True

    return False


def _content_timestamp(item: ContentItem):
    return item.published_at or item.fetched_at


def _normalize_archive_title(title: str | None) -> str:
    if not title:
        return ""
    normalized = unicodedata.normalize("NFKC", title).casefold()
    normalized = re.sub(r"[\W_]+", " ", normalized)
    return " ".join(normalized.split())


def _archive_dedupe_signature(item: ContentItem) -> tuple[str, str, str] | None:
    if item.source not in ARCHIVE_CONTENT_SOURCES:
        return None
    if not item.published_at:
        return None
    normalized_title = _normalize_archive_title(item.title)
    if not normalized_title:
        return None
    return ("day_title", item.published_at.date().isoformat(), normalized_title)


def _archive_source_rank(source: str) -> int:
    return ARCHIVE_SOURCE_PRIORITY.get(source, len(ARCHIVE_SOURCE_PRIORITY))


def _prefer_archive_item(existing: ContentItem, candidate: ContentItem) -> ContentItem:
    existing_rank = _archive_source_rank(existing.source)
    candidate_rank = _archive_source_rank(candidate.source)
    if existing_rank != candidate_rank:
        return existing if existing_rank < candidate_rank else candidate

    existing_timestamp = _content_timestamp(existing) or datetime.min
    candidate_timestamp = _content_timestamp(candidate) or datetime.min
    if existing_timestamp != candidate_timestamp:
        return existing if existing_timestamp > candidate_timestamp else candidate

    return existing if existing.id <= candidate.id else candidate


def _dedupe_archive_contents(contents: list[ContentItem]) -> list[ContentItem]:
    if get_settings().provider_mode == "mock":
        return contents

    chosen_by_signature: dict[tuple[str, str, str], ContentItem] = {}
    for item in contents:
        signature = _archive_dedupe_signature(item)
        if signature is None:
            continue
        existing = chosen_by_signature.get(signature)
        if existing is None:
            chosen_by_signature[signature] = item
            continue
        chosen_by_signature[signature] = _prefer_archive_item(existing, item)

    deduped: list[ContentItem] = []
    emitted_signatures: set[tuple[str, str, str]] = set()
    for item in contents:
        signature = _archive_dedupe_signature(item)
        if signature is None:
            deduped.append(item)
            continue
        chosen = chosen_by_signature.get(signature)
        if chosen is not item or signature in emitted_signatures:
            continue
        emitted_signatures.add(signature)
        deduped.append(item)

    return deduped


def _is_synthetic_json(raw_json: str | None) -> bool:
    if not raw_json:
        return False
    try:
        payload = json.loads(raw_json)
    except (TypeError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("synthetic") is True


def _filter_visible_contents(keyword: Keyword, contents: list[ContentItem]) -> list[ContentItem]:
    settings = get_settings()
    if settings.provider_mode == "mock":
        return contents

    visible: list[ContentItem] = []
    archive_queries = _archive_queries(keyword)
    gdelt_queries = archive_queries
    ambiguous_query_contexts = build_ambiguous_query_contexts(settings.archive_ambiguous_query_contexts_json)
    seen_gdelt_titles: set[str] = set()
    kept_gdelt_title_groups: list[tuple[date, set[str]]] = []

    for item in contents:
        if _is_synthetic_json(item.meta_json):
            continue
        if item.source == "direct_rss":
            if not any(
                archive_match_strength(
                    query,
                    title=item.title,
                    summary=item.summary,
                    url=item.url,
                )
                == "strong"
                for query in archive_queries
            ):
                continue
            visible.append(item)
            continue
        if item.source != "gdelt":
            visible.append(item)
            continue

        matched_query = next(
            (
                query
                for query in gdelt_queries
                if gdelt_matches_query(
                    query,
                    title=item.title,
                    url=item.url,
                    domain=item.author,
                    ambiguous_query_contexts=ambiguous_query_contexts,
                )
            ),
            None,
        )
        if not matched_query:
            continue

        title_key = gdelt_title_key(item.title)
        if title_key in seen_gdelt_titles:
            continue

        published_day = item.published_at.date() if item.published_at else None
        title_tokens = gdelt_title_token_set(item.title, matched_query)
        is_duplicate_story = (
            published_day is not None
            and bool(title_tokens)
            and any(
                kept_day == published_day and token_jaccard(title_tokens, kept_tokens) >= 0.82
                for kept_day, kept_tokens in kept_gdelt_title_groups
                if kept_tokens
            )
        )
        if is_duplicate_story:
            continue

        seen_gdelt_titles.add(title_key)
        if published_day is not None and title_tokens:
            kept_gdelt_title_groups.append((published_day, title_tokens))
        visible.append(item)

    return visible


def _build_archive_series_from_contents(contents: list[ContentItem], source: str) -> TrendSeriesPayload | None:
    counts_by_day: dict = {}
    for item in contents:
        if item.source != source or not item.published_at:
            continue
        bucket_start = item.published_at.replace(hour=0, minute=0, second=0, microsecond=0)
        counts_by_day[bucket_start] = counts_by_day.get(bucket_start, 0) + 1

    if not counts_by_day:
        return None

    return TrendSeriesPayload(
        source=source,
        metric="matched_item_count",
        source_type="timeline",
        points=[
            TrendPointPayload(bucket_start=bucket_start, value=float(count))
            for bucket_start, count in sorted(counts_by_day.items())
        ],
    )


def _build_keyword_history_series_from_contents(contents: list[ContentItem]) -> TrendSeriesPayload | None:
    counts_by_day: dict = {}
    deduped_contents = _dedupe_archive_contents(contents)

    for item in deduped_contents:
        if item.source not in KEYWORD_HISTORY_SOURCES or not item.published_at:
            continue
        bucket_start = item.published_at.replace(hour=0, minute=0, second=0, microsecond=0)
        counts_by_day[bucket_start] = counts_by_day.get(bucket_start, 0) + 1

    if not counts_by_day:
        return None

    return TrendSeriesPayload(
        source="keyword_history",
        metric="matched_item_count",
        source_type="timeline",
        points=[
            TrendPointPayload(bucket_start=bucket_start, value=float(count))
            for bucket_start, count in sorted(counts_by_day.items())
        ],
    )


def _replace_archive_series(
    series_payloads: list[TrendSeriesPayload],
    *,
    source: str,
    replacement: TrendSeriesPayload | None,
) -> list[TrendSeriesPayload]:
    filtered = [
        series
        for series in series_payloads
        if not (
            series.source == source
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
    ]
    if replacement is not None:
        filtered.append(replacement)
    filtered.sort(key=lambda series: (series.source, series.metric, series.source_type))
    return filtered


def _select_visible_content_items(
    keyword: Keyword,
    contents: list[ContentItem],
    *,
    days: int | None,
    parsed_content_source: str | None,
) -> list[ContentItem]:
    visible = _filter_content(_filter_visible_contents(keyword, contents), days)
    if parsed_content_source:
        if parsed_content_source in ARCHIVE_CONTENT_SOURCES:
            visible = _dedupe_archive_contents(visible)
        return visible[:20]
    if keyword.kind not in {"keyword", "github_repo"}:
        return visible[:20]

    archive_items = _dedupe_archive_contents([item for item in visible if item.source in ARCHIVE_CONTENT_SOURCES])
    other_items = [item for item in visible if item.source not in ARCHIVE_CONTENT_SOURCES]
    if keyword.kind == "github_repo":
        github_items = [item for item in other_items if item.source == "github"]
        news_items = [item for item in other_items if item.source != "github"]
        selected = github_items[:8] + archive_items[:8] + news_items[:4]
    else:
        selected = archive_items[:12] + other_items[:8]
    selected.sort(key=_content_timestamp, reverse=True)
    return selected[:20]


def _create_job(
    db: Session,
    keyword: Keyword,
    *,
    need_github_history: bool,
    need_github_content: bool,
    need_newsnow: bool,
) -> BackfillJob:
    job = BackfillJob(keyword_id=keyword.id, status="pending")
    db.add(job)
    db.flush()

    if need_github_history:
        db.add(BackfillJobTask(job_id=job.id, source="github", task_type="history", status="pending"))
    if need_github_content:
        db.add(BackfillJobTask(job_id=job.id, source="github", task_type="content", status="pending"))
    if need_newsnow:
        db.add(BackfillJobTask(job_id=job.id, source="newsnow", task_type="snapshot", status="pending"))

    db.commit()
    db.refresh(job)
    return _latest_job(db, keyword.id) or job


def _maybe_schedule_backfill(
    db: Session,
    background_tasks: BackgroundTasks,
    keyword: Keyword,
    *,
    retry_failed: bool = False,
) -> BackfillJob | None:
    active_job = db.scalar(
        select(BackfillJob)
        .options(selectinload(BackfillJob.tasks))
        .where(
            BackfillJob.keyword_id == keyword.id,
            BackfillJob.status.in_(("pending", "running")),
        )
        .order_by(desc(BackfillJob.requested_at))
    )
    if active_job:
        return active_job

    need_github_history = keyword.kind == "github_repo" and not _has_github_history(db, keyword.id)
    need_github_content = keyword.kind == "github_repo" and not _has_fresh_content_items(db, keyword.id, "github")
    need_newsnow = keyword.kind == "github_repo" and not _has_fresh_newsnow_snapshot(db, keyword.id)

    latest_job = _latest_job(db, keyword.id)
    if latest_job and latest_job.status in {"failed", "partial"} and not retry_failed:
        if need_github_history or need_github_content or need_newsnow:
            return latest_job
        return None

    if not need_github_history and not need_github_content and not need_newsnow:
        return latest_job

    job = _create_job(
        db,
        keyword,
        need_github_history=need_github_history,
        need_github_content=need_github_content,
        need_newsnow=need_newsnow,
    )
    background_tasks.add_task(run_backfill_job, job.id)
    return job


def _build_snapshot(points: list[TrendPoint], contents: list[ContentItem]) -> SnapshotPayload:
    latest_by_metric: dict[tuple[str, str], TrendPoint] = {}
    for point in sorted(points, key=lambda item: (item.bucket_start, item.collected_at), reverse=True):
        latest_by_metric.setdefault((point.source, point.metric), point)

    github_point = latest_by_metric.get(("github", "star_delta"))
    news_hits = latest_by_metric.get(("newsnow", "hot_hit_count"))
    news_platforms = latest_by_metric.get(("newsnow", "platform_count"))
    newsnow_content_count = sum(1 for item in contents if item.source == "newsnow")
    updated_candidates = [point.collected_at for point in latest_by_metric.values()]
    updated_at = max(updated_candidates) if updated_candidates else None

    return SnapshotPayload(
        github_star_today=int(github_point.value) if github_point else None,
        newsnow_platform_count=int(news_platforms.value) if news_platforms else None,
        newsnow_item_count=int(news_hits.value) if news_hits else newsnow_content_count or None,
        updated_at=updated_at,
    )


def _build_series(points: list[TrendPoint]) -> list[TrendSeriesPayload]:
    ordered = sorted(points, key=lambda item: (item.source, item.metric, item.source_type, item.bucket_start))
    series_payloads: list[TrendSeriesPayload] = []

    for key, grouped in groupby(ordered, key=lambda item: (item.source, item.metric, item.source_type)):
        source, metric, source_type = key
        group_points = [
            TrendPointPayload(bucket_start=point.bucket_start, value=point.value) for point in grouped if metric != "platform_count"
        ]
        if not group_points:
            continue
        series_payloads.append(
            TrendSeriesPayload(
                source=source,
                metric=metric,
                source_type=source_type,
                points=group_points,
            )
        )

    return series_payloads


def _apply_trend_semantics(keyword: Keyword, series_payloads: list[TrendSeriesPayload]) -> list[TrendSeriesPayload]:
    if keyword.kind != "keyword":
        return series_payloads

    has_keyword_timeline = any(
        series.metric == "matched_item_count" and series.source_type == "timeline"
        for series in series_payloads
    )
    transformed: list[TrendSeriesPayload] = []
    for series in series_payloads:
        if has_keyword_timeline and series.source == "newsnow" and series.metric == "hot_hit_count":
            continue
        if series.source != "newsnow" or series.metric != "hot_hit_count":
            transformed.append(series)
            continue

        running_total = 0.0
        cumulative_points: list[TrendPointPayload] = []
        for point in series.points:
            running_total += point.value
            cumulative_points.append(TrendPointPayload(bucket_start=point.bucket_start, value=running_total))

        transformed.append(
            TrendSeriesPayload(
                source=series.source,
                metric=series.metric,
                source_type=series.source_type,
                points=cumulative_points,
            )
        )

    return transformed


def _filter_period(points: list[TrendPoint], days: int | None) -> list[TrendPoint]:
    if days is None:
        return points
    threshold = utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    return [point for point in points if point.bucket_start >= threshold]


def _filter_content(contents: list[ContentItem], days: int | None) -> list[ContentItem]:
    if days is None:
        return contents
    threshold = utcnow() - timedelta(days=days)
    return [item for item in contents if not item.published_at or item.published_at >= threshold]


def _availability(keyword: Keyword, job: BackfillJob | None, points: list[TrendPoint], contents: list[ContentItem]) -> dict[str, str]:
    availability = {
        "github_history": "missing",
        "newsnow_snapshot": "missing",
        "google_news_archive": "missing",
        "direct_rss_archive": "missing",
        "gdelt_archive": "missing",
    }

    if any(point.source == "github" and point.metric == "star_delta" for point in points):
        availability["github_history"] = "ready"
    if any(point.source == "newsnow" for point in points):
        availability["newsnow_snapshot"] = "ready"
    if any(point.source == "google_news" and point.metric == "matched_item_count" for point in points):
        availability["google_news_archive"] = "ready"
    elif any(item.source == "google_news" for item in contents):
        availability["google_news_archive"] = "ready"
    if any(point.source == "direct_rss" and point.metric == "matched_item_count" for point in points):
        availability["direct_rss_archive"] = "ready"
    elif any(item.source == "direct_rss" for item in contents):
        availability["direct_rss_archive"] = "ready"
    if any(point.source == "gdelt" and point.metric == "matched_item_count" for point in points):
        availability["gdelt_archive"] = "ready"
    elif any(item.source == "gdelt" for item in contents):
        availability["gdelt_archive"] = "ready"

    if job:
        for task in job.tasks:
            if task.source == "github" and task.task_type == "history":
                availability["github_history"] = (
                    "ready" if task.status == "success" else "not_applicable" if task.status == "skipped" else task.status
                )
            elif task.source == "newsnow":
                availability["newsnow_snapshot"] = "ready" if task.status == "success" else task.status

    if keyword.kind != "github_repo" and availability["github_history"] == "missing":
        availability["github_history"] = "not_applicable"
    if (
        keyword.kind == "keyword"
        and availability["newsnow_snapshot"] == "missing"
        and any(point.metric == "matched_item_count" and point.source_type == "timeline" for point in points)
    ):
        availability["newsnow_snapshot"] = "not_applicable"
    if keyword.kind not in {"keyword", "github_repo"} and availability["google_news_archive"] == "missing":
        availability["google_news_archive"] = "not_applicable"
    if keyword.kind not in {"keyword", "github_repo"} and availability["direct_rss_archive"] == "missing":
        availability["direct_rss_archive"] = "not_applicable"
    if keyword.kind not in {"keyword", "github_repo"} and availability["gdelt_archive"] == "missing":
        availability["gdelt_archive"] = "not_applicable"

    return availability


def _serialize_job(job: BackfillJob | None) -> BackfillJobPayload | None:
    if not job:
        return None
    return BackfillJobPayload(
        id=job.id,
        status=job.status,
        error_message=job.error_message,
        tasks=[
            BackfillTaskPayload(
                source=task.source,
                task_type=task.task_type,
                status=task.status,
                message=task.message,
            )
            for task in job.tasks
        ],
    )


def search_keyword(
    db: Session,
    background_tasks: BackgroundTasks,
    query: str,
    period: str,
    content_source: str = "all",
    retry_failed: bool = False,
) -> SearchResponsePayload:
    days = parse_period(period)
    parsed_content_source = parse_content_source(content_source)
    target = resolve_search_query(query, repo_lookup=resolve_github_repo_name)
    keyword = get_or_create_keyword(db, target)
    _prefetch_content_history_inline(db, keyword)
    job = _maybe_schedule_backfill(
        db,
        background_tasks,
        keyword,
        retry_failed=retry_failed,
    )

    db.refresh(keyword)

    trend_points = list(
        db.scalars(
            select(TrendPoint)
            .where(TrendPoint.keyword_id == keyword.id)
            .order_by(TrendPoint.bucket_start.asc())
        )
    )

    snapshot_contents = list(
        db.scalars(
            select(ContentItem)
            .where(ContentItem.keyword_id == keyword.id)
            .order_by(desc(ContentItem.published_at), desc(ContentItem.fetched_at))
            .limit(20)
        )
    )
    archive_history_contents = list(
        db.scalars(
            select(ContentItem)
            .where(
                ContentItem.keyword_id == keyword.id,
                ContentItem.source.in_(ARCHIVE_CONTENT_SOURCES),
                ContentItem.published_at.is_not(None),
            )
            .order_by(ContentItem.published_at.asc(), ContentItem.id.asc())
        )
    )
    keyword_history_contents: list[ContentItem] = []
    if keyword.kind == "keyword":
        keyword_history_contents = list(
            db.scalars(
                select(ContentItem)
                .where(
                    ContentItem.keyword_id == keyword.id,
                    ContentItem.source.in_(tuple(sorted(KEYWORD_HISTORY_SOURCES))),
                    ContentItem.published_at.is_not(None),
                )
                .order_by(ContentItem.published_at.asc(), ContentItem.id.asc())
            )
        )
    content_stmt = (
        select(ContentItem)
        .where(ContentItem.keyword_id == keyword.id)
        .order_by(desc(ContentItem.published_at), desc(ContentItem.fetched_at))
    )
    if parsed_content_source:
        content_stmt = content_stmt.where(ContentItem.source == parsed_content_source)
    content_limit = 120 if parsed_content_source is None else 20
    content_items = list(db.scalars(content_stmt.limit(content_limit)))

    filtered_points = _filter_period(trend_points, days)
    filtered_contents = _select_visible_content_items(
        keyword,
        content_items,
        days=days,
        parsed_content_source=parsed_content_source,
    )
    filtered_archive_history_contents = _filter_content(
        _filter_visible_contents(keyword, archive_history_contents),
        days,
    )
    filtered_keyword_history_contents = _filter_content(
        _filter_visible_contents(keyword, keyword_history_contents),
        days,
    )
    series = _build_series(filtered_points)
    for source in ARCHIVE_CONTENT_SOURCES:
        series = _replace_archive_series(
            series,
            source=source,
            replacement=_build_archive_series_from_contents(filtered_archive_history_contents, source),
        )
    if keyword.kind == "keyword":
        series = _replace_archive_series(
            series,
            source="keyword_history",
            replacement=_build_keyword_history_series_from_contents(filtered_keyword_history_contents),
        )
    series = _apply_trend_semantics(keyword, series)
    snapshot = _build_snapshot(trend_points, snapshot_contents)
    availability = _availability(keyword, job, trend_points, snapshot_contents)

    series_points = [point.bucket_start for item in series for point in item.points]
    period_start = min(series_points) if series_points else None
    period_end = max(series_points) if series_points else None

    return SearchResponsePayload(
        keyword=KeywordPayload.model_validate(keyword),
        availability=availability,
        snapshot=snapshot,
        trend=TrendPayload(
            period=TrendPeriodPayload(start=period_start, end=period_end),
            series=series,
        ),
        content_items=[ContentItemPayload.model_validate(item) for item in filtered_contents],
        backfill_job=_serialize_job(job),
    )


def get_backfill_status(db: Session, keyword_id: int) -> BackfillStatusPayload:
    job = _latest_job(db, keyword_id)
    if not job:
        raise HTTPException(status_code=404, detail="Backfill job not found.")

    return BackfillStatusPayload(
        job_id=job.id,
        status=job.status,
        tasks=[
            BackfillTaskPayload(
                source=task.source,
                task_type=task.task_type,
                status=task.status,
                message=task.message,
            )
            for task in job.tasks
        ],
    )


def set_track_state(db: Session, keyword_id: int, tracked: bool) -> KeywordPayload:
    keyword = db.scalar(select(Keyword).where(Keyword.id == keyword_id))
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found.")

    keyword.is_tracked = tracked
    keyword.updated_at = utcnow()
    db.commit()
    db.refresh(keyword)
    return KeywordPayload.model_validate(keyword)
