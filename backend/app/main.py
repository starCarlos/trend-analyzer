from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.schemas import (
    BackfillStatusPayload,
    CollectRunPayload,
    SchedulerStatusPayload,
    CollectTriggerRequest,
    CollectTriggerResponse,
    KeywordCreateRequest,
    KeywordPayload,
    ProviderSmokePayload,
    ProviderSmokeRequest,
    ProviderStatusPayload,
    ProviderVerifyPayload,
    ProviderVerifyRequest,
    SearchResponsePayload,
    TrackPayload,
)
from app.services.collector import create_keyword_entry, init_db, trigger_collection
from app.services.management import list_collect_runs, list_keywords
from app.services.provider_diagnostics import get_provider_status
from app.services.provider_smoke import run_provider_smoke
from app.services.provider_verification import verify_provider_connectivity
from app.services.scheduler import CollectionScheduler
from app.services.search import get_backfill_status, search_keyword, set_track_state


settings = get_settings()
scheduler = CollectionScheduler(
    job_runner=trigger_collection,
    enabled=settings.scheduler_enabled,
    interval_seconds=settings.scheduler_interval_seconds,
    initial_delay_seconds=settings.scheduler_initial_delay_seconds,
    period=settings.scheduler_period,
    run_backfill_now=settings.scheduler_run_backfill_now,
)
web_dir = Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

allow_origins = list(
    dict.fromkeys(
        [
            settings.frontend_origin,
            "http://127.0.0.1:5081",
            "http://localhost:5081",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ]
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=web_dir), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(web_dir / "index.html")


@app.get("/tracked", include_in_schema=False)
def tracked_page() -> FileResponse:
    return FileResponse(web_dir / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "scheduler_enabled": settings.scheduler_enabled,
        "provider_mode": settings.provider_mode,
    }


@app.get("/api/search", response_model=SearchResponsePayload)
def search(
    q: str,
    background_tasks: BackgroundTasks,
    period: str = "30d",
    content_source: str = "all",
    db: Session = Depends(get_db),
) -> SearchResponsePayload:
    return search_keyword(
        db=db,
        background_tasks=background_tasks,
        query=q,
        period=period,
        content_source=content_source,
    )


@app.get("/api/keywords/{keyword_id}/backfill-status", response_model=BackfillStatusPayload)
def backfill_status(keyword_id: int, db: Session = Depends(get_db)) -> BackfillStatusPayload:
    return get_backfill_status(db, keyword_id)


@app.get("/api/keywords", response_model=list[KeywordPayload])
def keywords(tracked_only: bool = False) -> list[KeywordPayload]:
    return list_keywords(tracked_only=tracked_only)


@app.post("/api/keywords", response_model=SearchResponsePayload)
def create_keyword(payload: KeywordCreateRequest) -> SearchResponsePayload:
    return create_keyword_entry(
        payload.query,
        track=payload.track,
        period=payload.period,
        run_backfill_now=payload.run_backfill_now,
    )


@app.post("/api/keywords/{keyword_id}/track", response_model=TrackPayload)
def track_keyword(keyword_id: int, db: Session = Depends(get_db)) -> TrackPayload:
    return TrackPayload(keyword=set_track_state(db, keyword_id, tracked=True))


@app.delete("/api/keywords/{keyword_id}/track", response_model=TrackPayload)
def untrack_keyword(keyword_id: int, db: Session = Depends(get_db)) -> TrackPayload:
    return TrackPayload(keyword=set_track_state(db, keyword_id, tracked=False))


@app.post("/api/collect/trigger", response_model=CollectTriggerResponse)
def collect_trigger(payload: CollectTriggerRequest) -> CollectTriggerResponse:
    return trigger_collection(
        query=payload.query,
        tracked_only=payload.tracked_only,
        period=payload.period,
        run_backfill_now=payload.run_backfill_now,
    )


@app.get("/api/collect/logs", response_model=list[CollectRunPayload])
def collect_logs(limit: int = 50) -> list[CollectRunPayload]:
    return list_collect_runs(limit=limit)


@app.get("/api/collect/status", response_model=SchedulerStatusPayload)
def collect_status() -> SchedulerStatusPayload:
    snapshot = scheduler.snapshot()
    return SchedulerStatusPayload(**asdict(snapshot))


@app.get("/api/provider-status", response_model=ProviderStatusPayload)
def provider_status() -> ProviderStatusPayload:
    return get_provider_status()


@app.post("/api/provider-verify", response_model=ProviderVerifyPayload)
def provider_verify(payload: ProviderVerifyRequest) -> ProviderVerifyPayload:
    return verify_provider_connectivity(probe_mode=payload.probe_mode)


@app.post("/api/provider-smoke", response_model=ProviderSmokePayload)
def provider_smoke(payload: ProviderSmokeRequest) -> ProviderSmokePayload:
    return run_provider_smoke(
        query=payload.query,
        period=payload.period,
        probe_mode=payload.probe_mode,
        force_search=payload.force_search,
    )
