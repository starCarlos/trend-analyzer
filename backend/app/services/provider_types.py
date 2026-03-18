from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TrendPointInput:
    source: str
    metric: str
    source_type: str
    bucket_granularity: str
    bucket_start: datetime
    value: float
    raw_json: str


@dataclass(slots=True)
class ContentItemInput:
    source: str
    source_type: str
    external_key: str
    title: str
    url: str | None
    summary: str | None
    author: str | None
    published_at: datetime | None
    meta_json: str
