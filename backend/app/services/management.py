from __future__ import annotations

from sqlalchemy import desc, select

from app.database import SessionLocal
from app.models import CollectRun, Keyword
from app.schemas import CollectRunPayload, KeywordPayload


def list_keywords(*, tracked_only: bool = False) -> list[KeywordPayload]:
    db = SessionLocal()
    try:
        stmt = select(Keyword).order_by(desc(Keyword.updated_at), desc(Keyword.id))
        if tracked_only:
            stmt = stmt.where(Keyword.is_tracked.is_(True))
        keywords = list(db.scalars(stmt))
        return [KeywordPayload.model_validate(keyword) for keyword in keywords]
    finally:
        db.close()


def list_collect_runs(*, limit: int = 50) -> list[CollectRunPayload]:
    db = SessionLocal()
    try:
        runs = list(
            db.scalars(
                select(CollectRun)
                .order_by(desc(CollectRun.created_at), desc(CollectRun.id))
                .limit(limit)
            )
        )
        return [CollectRunPayload.model_validate(run) for run in runs]
    finally:
        db.close()
