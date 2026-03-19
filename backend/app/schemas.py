from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


LEGACY_PROVIDER_FIELDS = ("github", "newsnow", "google_news", "direct_rss", "gdelt")


class KeywordPayload(BaseModel):
    id: int
    raw_query: str
    normalized_query: str
    kind: str
    is_tracked: bool
    target_ref: str | None = None
    first_seen_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TrendPointPayload(BaseModel):
    bucket_start: datetime
    value: float


class TrendSeriesPayload(BaseModel):
    source: str
    metric: str
    source_type: str
    points: list[TrendPointPayload]


class TrendPeriodPayload(BaseModel):
    start: datetime | None = None
    end: datetime | None = None


class TrendPayload(BaseModel):
    period: TrendPeriodPayload
    series: list[TrendSeriesPayload]


class SnapshotPayload(BaseModel):
    github_star_today: int | None = None
    newsnow_platform_count: int | None = None
    newsnow_item_count: int | None = None
    updated_at: datetime | None = None


class ContentItemPayload(BaseModel):
    id: int
    source: str
    source_type: str
    title: str
    url: str | None = None
    summary: str | None = None
    author: str | None = None
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BackfillTaskPayload(BaseModel):
    source: str
    task_type: str
    status: str
    message: str | None = None


class BackfillJobPayload(BaseModel):
    id: int
    status: str
    error_message: str | None = None
    tasks: list[BackfillTaskPayload] = []


class SearchResponsePayload(BaseModel):
    keyword: KeywordPayload
    availability: dict[str, str]
    snapshot: SnapshotPayload
    trend: TrendPayload
    content_items: list[ContentItemPayload]
    backfill_job: BackfillJobPayload | None = None


class BackfillStatusPayload(BaseModel):
    job_id: int
    status: str
    tasks: list[BackfillTaskPayload]


class TrackPayload(BaseModel):
    keyword: KeywordPayload


class KeywordCreateRequest(BaseModel):
    query: str
    track: bool = False
    period: str = "30d"
    run_backfill_now: bool = False


class CollectTriggerRequest(BaseModel):
    query: str | None = None
    tracked_only: bool = True
    period: str = "30d"
    run_backfill_now: bool = True


class CollectRunPayload(BaseModel):
    id: int
    keyword_id: int | None = None
    source: str
    run_type: str
    status: str
    duration_ms: int | None = None
    message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollectTriggerResultPayload(BaseModel):
    query: str
    keyword_id: int
    status: str
    tracked: bool


class CollectTriggerResponse(BaseModel):
    triggered_count: int
    results: list[CollectTriggerResultPayload]


class SchedulerStatusPayload(BaseModel):
    enabled: bool
    running: bool
    interval_seconds: int
    initial_delay_seconds: int
    period: str
    run_backfill_now: bool
    iteration_count: int
    last_started_at: str | None = None
    last_finished_at: str | None = None
    last_status: str
    last_error: str | None = None
    last_triggered_count: int


class ProviderCheckPayload(BaseModel):
    source: str
    mode: str
    preferred_provider: str
    fallback_provider: str | None = None
    status: str
    can_use_real_provider: bool
    issues: list[str] = []
    notes: list[str] = []


class ProviderStatusPayload(BaseModel):
    requested_mode: str
    resolved_provider: str
    summary: str
    providers: list[ProviderCheckPayload] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_provider_fields(cls, data):
        if not isinstance(data, dict):
            return data
        if "providers" in data and data["providers"] is not None:
            return data

        payload = dict(data)
        payload["providers"] = [payload.pop(field) for field in LEGACY_PROVIDER_FIELDS if payload.get(field) is not None]
        return payload

    def get_provider(self, source: str) -> ProviderCheckPayload | None:
        return next((provider for provider in self.providers if provider.source == source), None)

    @property
    def github(self) -> ProviderCheckPayload | None:
        return self.get_provider("github")

    @property
    def newsnow(self) -> ProviderCheckPayload | None:
        return self.get_provider("newsnow")

    @property
    def google_news(self) -> ProviderCheckPayload | None:
        return self.get_provider("google_news")

    @property
    def direct_rss(self) -> ProviderCheckPayload | None:
        return self.get_provider("direct_rss")

    @property
    def gdelt(self) -> ProviderCheckPayload | None:
        return self.get_provider("gdelt")


class ProviderVerifyRequest(BaseModel):
    probe_mode: Literal["current", "real"] = "real"


class ProviderProbePayload(BaseModel):
    source: str
    attempted_provider: str
    status: str
    endpoint: str | None = None
    message: str


class ProviderVerifyPayload(BaseModel):
    probe_mode: str
    requested_mode: str
    effective_mode: str
    summary: str
    providers: list[ProviderProbePayload] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_provider_fields(cls, data):
        if not isinstance(data, dict):
            return data
        if "providers" in data and data["providers"] is not None:
            return data

        payload = dict(data)
        payload["providers"] = [payload.pop(field) for field in LEGACY_PROVIDER_FIELDS if payload.get(field) is not None]
        return payload

    def get_provider(self, source: str) -> ProviderProbePayload | None:
        return next((provider for provider in self.providers if provider.source == source), None)

    @property
    def github(self) -> ProviderProbePayload | None:
        return self.get_provider("github")

    @property
    def newsnow(self) -> ProviderProbePayload | None:
        return self.get_provider("newsnow")

    @property
    def google_news(self) -> ProviderProbePayload | None:
        return self.get_provider("google_news")

    @property
    def direct_rss(self) -> ProviderProbePayload | None:
        return self.get_provider("direct_rss")

    @property
    def gdelt(self) -> ProviderProbePayload | None:
        return self.get_provider("gdelt")


class ProviderSmokeRequest(BaseModel):
    query: str = "openai/openai-python"
    period: str = "30d"
    probe_mode: Literal["current", "real"] = "real"
    force_search: bool = False


class ProviderSmokeSearchPayload(BaseModel):
    query: str
    period: str
    status: str
    message: str
    keyword_kind: str | None = None
    normalized_query: str | None = None
    trend_series_count: int = 0
    content_item_count: int = 0
    availability: dict[str, str] = {}
    backfill_status: str | None = None


class ProviderSmokePayload(BaseModel):
    query: str
    period: str
    probe_mode: str
    force_search: bool
    summary: str
    provider_status: ProviderStatusPayload
    provider_verify: ProviderVerifyPayload
    search: ProviderSmokeSearchPayload
    next_steps: list[str] = []
