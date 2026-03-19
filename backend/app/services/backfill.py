import json
from time import perf_counter

from sqlalchemy import select

from app.database import SessionLocal
from app.models import BackfillJob, BackfillJobTask, CollectRun, ContentItem, Keyword, TrendPoint, utcnow
from app.services.provider_registry import ARCHIVE_PROVIDER_FETCHERS
from app.services.providers import get_data_provider
from app.services.provider_types import ContentItemInput, TrendPointInput


def _upsert_trend_point(session, keyword_id: int, point) -> None:
    existing = session.scalar(
        select(TrendPoint).where(
            TrendPoint.keyword_id == keyword_id,
            TrendPoint.source == point.source,
            TrendPoint.metric == point.metric,
            TrendPoint.source_type == point.source_type,
            TrendPoint.bucket_granularity == point.bucket_granularity,
            TrendPoint.bucket_start == point.bucket_start,
        )
    )

    if existing:
        existing.value = point.value
        existing.raw_json = point.raw_json
        existing.collected_at = utcnow()
        return

    session.add(
        TrendPoint(
            keyword_id=keyword_id,
            source=point.source,
            metric=point.metric,
            source_type=point.source_type,
            bucket_granularity=point.bucket_granularity,
            bucket_start=point.bucket_start,
            value=point.value,
            raw_json=point.raw_json,
        )
    )


def _upsert_content_item(session, keyword_id: int, item) -> None:
    existing = session.scalar(
        select(ContentItem).where(
            ContentItem.source == item.source,
            ContentItem.external_key == item.external_key,
        )
    )

    if existing:
        existing.title = item.title
        existing.url = item.url
        existing.summary = item.summary
        existing.author = item.author
        existing.published_at = item.published_at
        existing.meta_json = item.meta_json
        existing.fetched_at = utcnow()
        return

    session.add(
        ContentItem(
            keyword_id=keyword_id,
            source=item.source,
            source_type=item.source_type,
            external_key=item.external_key,
            title=item.title,
            url=item.url,
            summary=item.summary,
            author=item.author,
            published_at=item.published_at,
            meta_json=item.meta_json,
        )
    )


KEYWORD_HISTORY_SOURCES = {"newsnow", "google_news", "direct_rss", "gdelt"}


def _derive_keyword_history_points(session, keyword: Keyword) -> list[TrendPointInput]:
    if keyword.kind != "keyword":
        return []

    content_items = list(
        session.scalars(
            select(ContentItem)
            .where(
                ContentItem.keyword_id == keyword.id,
                ContentItem.source.in_(tuple(sorted(KEYWORD_HISTORY_SOURCES))),
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
            "derived_from": "dated_content_items",
            "sources": sorted({item.source for item in content_items if item.source in KEYWORD_HISTORY_SOURCES}),
            "content_item_count": len(content_items),
            "bucket_count": len(counts_by_day),
        }
    )

    return [
        TrendPointInput(
            source="keyword_history",
            metric="matched_item_count",
            source_type="timeline",
            bucket_granularity="day",
            bucket_start=bucket_start,
            value=float(count),
            raw_json=raw_json,
        )
        for bucket_start, count in sorted(counts_by_day.items())
    ]


def _mark_task(task: BackfillJobTask, status: str, message: str | None = None) -> None:
    now = utcnow()
    if status == "running" and task.started_at is None:
        task.started_at = now
    if status in {"success", "failed", "skipped"}:
        task.finished_at = now
    task.status = status
    task.message = message


def _finalize_job(job: BackfillJob) -> None:
    statuses = [task.status for task in job.tasks]
    if statuses and all(status == "success" for status in statuses):
        job.status = "success"
        job.error_message = None
    elif any(status == "success" for status in statuses):
        job.status = "partial"
        job.error_message = "One or more providers failed."
    else:
        job.status = "failed"
        job.error_message = "All providers failed."
    job.finished_at = utcnow()


def run_backfill_job(job_id: int) -> None:
    session = SessionLocal()
    try:
        provider = get_data_provider()
        job = session.scalar(select(BackfillJob).where(BackfillJob.id == job_id))
        if not job:
            return

        keyword = session.scalar(select(Keyword).where(Keyword.id == job.keyword_id))
        if not keyword:
            job.status = "failed"
            job.error_message = "Keyword not found."
            session.commit()
            return

        job.status = "running"
        job.started_at = utcnow()
        session.commit()

        for task in job.tasks:
            started = perf_counter()
            try:
                _mark_task(task, "running")
                session.commit()

                if task.source == "github" and task.task_type == "history":
                    if keyword.kind != "github_repo" or not keyword.target_ref:
                        _mark_task(task, "skipped", "Not a GitHub repository query.")
                    else:
                        points = provider.fetch_github_history(keyword.target_ref)
                        for point in points:
                            _upsert_trend_point(session, keyword.id, point)
                        _mark_task(task, "success", f"Stored {len(points)} history points via {provider.name}.")

                elif task.source == "github" and task.task_type == "content":
                    if keyword.kind != "github_repo" or not keyword.target_ref:
                        _mark_task(task, "skipped", "Not a GitHub repository query.")
                    else:
                        content_items = provider.fetch_github_content(keyword.target_ref)
                        for item in content_items:
                            _upsert_content_item(session, keyword.id, item)
                        _mark_task(
                            task,
                            "success",
                            f"Stored {len(content_items)} content items via {provider.name}.",
                        )

                elif task.source == "newsnow" and task.task_type == "snapshot":
                    trend_points, content_items = provider.fetch_newsnow_snapshot(keyword.normalized_query)
                    archive_items: list[ContentItemInput] = []
                    archive_errors: list[str] = []
                    archive_counts: dict[str, int] = {}
                    if keyword.kind == "keyword":
                        for source, fetcher_name in ARCHIVE_PROVIDER_FETCHERS:
                            archive_fetcher = getattr(provider, fetcher_name, None)
                            if not callable(archive_fetcher):
                                continue
                            try:
                                fetched = archive_fetcher(keyword.normalized_query)
                            except Exception as exc:
                                archive_errors.append(f"{source}: {exc}")
                                continue
                            archive_counts[source] = len(fetched)
                            archive_items.extend(fetched)
                    for point in trend_points:
                        _upsert_trend_point(session, keyword.id, point)
                    for item in content_items:
                        _upsert_content_item(session, keyword.id, item)
                    for item in archive_items:
                        _upsert_content_item(session, keyword.id, item)
                    # SessionLocal disables autoflush, so flush inserted content items
                    # before deriving history buckets from the accumulated content set.
                    session.flush()
                    for point in _derive_keyword_history_points(session, keyword):
                        _upsert_trend_point(session, keyword.id, point)
                    message = (
                        f"Stored {len(trend_points)} points and {len(content_items) + len(archive_items)} "
                        f"content items via {provider.name}."
                    )
                    if archive_counts:
                        added_summary = ", ".join(
                            f"{source}={count}" for source, count in sorted(archive_counts.items()) if count > 0
                        )
                        if added_summary:
                            message += f" Added historical archive items: {added_summary}."
                    if archive_errors:
                        message += f" Historical archive skipped: {'；'.join(archive_errors)}."
                    _mark_task(
                        task,
                        "success",
                        message,
                    )
                else:
                    _mark_task(task, "skipped", "Task type is not implemented.")

                duration_ms = int((perf_counter() - started) * 1000)
                session.add(
                    CollectRun(
                        keyword_id=keyword.id,
                        source=task.source,
                        run_type="backfill",
                        status="success" if task.status == "success" else "partial",
                        duration_ms=duration_ms,
                        message=task.message,
                    )
                )
                session.commit()
            except Exception as exc:  # pragma: no cover - defensive branch
                duration_ms = int((perf_counter() - started) * 1000)
                _mark_task(task, "failed", str(exc))
                session.add(
                    CollectRun(
                        keyword_id=keyword.id,
                        source=task.source,
                        run_type="backfill",
                        status="failed",
                        duration_ms=duration_ms,
                        message=str(exc),
                    )
                )
                session.commit()

        _finalize_job(job)
        session.commit()
    finally:
        session.close()
