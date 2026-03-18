from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Keyword
from app.schemas import (
    CollectTriggerResponse,
    CollectTriggerResultPayload,
    KeywordPayload,
    SearchResponsePayload,
)
from app.services.backfill import run_backfill_job
from app.services.search import search_keyword, set_track_state


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def refresh_keyword(query: str, period: str = "30d", run_backfill_now: bool = True) -> SearchResponsePayload:
    init_db()
    db = SessionLocal()
    try:
        initial = search_keyword(
            db=db,
            background_tasks=BackgroundTasks(),
            query=query,
            period=period,
            retry_failed=True,
        )
        job_id = initial.backfill_job.id if initial.backfill_job else None
    finally:
        db.close()

    if run_backfill_now and job_id and initial.backfill_job.status in {"pending", "running"}:
        run_backfill_job(job_id)

    db = SessionLocal()
    try:
        return search_keyword(
            db=db,
            background_tasks=BackgroundTasks(),
            query=query,
            period=period,
            retry_failed=False,
        )
    finally:
        db.close()


def ensure_tracked(query: str) -> KeywordPayload:
    init_db()
    db = SessionLocal()
    try:
        payload = search_keyword(
            db=db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="30d",
        )
        return set_track_state(db, payload.keyword.id, tracked=True)
    finally:
        db.close()


def list_tracked_keywords() -> list[KeywordPayload]:
    init_db()
    db = SessionLocal()
    try:
        return _list_keywords(db, tracked_only=True)
    finally:
        db.close()


def collect_tracked_keywords(period: str = "30d") -> list[SearchResponsePayload]:
    tracked = list_tracked_keywords()
    results: list[SearchResponsePayload] = []
    for keyword in tracked:
        results.append(refresh_keyword(keyword.raw_query, period=period, run_backfill_now=True))
    return results


def create_keyword_entry(
    query: str,
    *,
    track: bool = False,
    period: str = "30d",
    run_backfill_now: bool = False,
) -> SearchResponsePayload:
    payload = refresh_keyword(query, period=period, run_backfill_now=run_backfill_now)
    if track:
        ensure_tracked(query)
        payload.keyword.is_tracked = True
    return payload


def trigger_collection(
    *,
    query: str | None = None,
    tracked_only: bool = True,
    period: str = "30d",
    run_backfill_now: bool = True,
) -> CollectTriggerResponse:
    results: list[CollectTriggerResultPayload] = []

    if query:
        payload = refresh_keyword(query, period=period, run_backfill_now=run_backfill_now)
        results.append(
            CollectTriggerResultPayload(
                query=payload.keyword.raw_query,
                keyword_id=payload.keyword.id,
                status=payload.backfill_job.status if payload.backfill_job else "ready",
                tracked=payload.keyword.is_tracked,
            )
        )
        return CollectTriggerResponse(triggered_count=len(results), results=results)

    db = SessionLocal()
    try:
        keywords = _list_keywords(db, tracked_only=tracked_only)
    finally:
        db.close()
    for keyword in keywords:
        payload = refresh_keyword(keyword.raw_query, period=period, run_backfill_now=run_backfill_now)
        results.append(
            CollectTriggerResultPayload(
                query=payload.keyword.raw_query,
                keyword_id=payload.keyword.id,
                status=payload.backfill_job.status if payload.backfill_job else "ready",
                tracked=payload.keyword.is_tracked,
            )
        )

    return CollectTriggerResponse(triggered_count=len(results), results=results)


def _list_keywords(db, *, tracked_only: bool) -> list[KeywordPayload]:
    stmt = select(Keyword).order_by(Keyword.updated_at.desc(), Keyword.id.desc())
    if tracked_only:
        stmt = stmt.where(Keyword.is_tracked.is_(True))
    keywords = list(db.scalars(stmt))
    return [KeywordPayload.model_validate(keyword) for keyword in keywords]
