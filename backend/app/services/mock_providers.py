from datetime import timedelta
import hashlib
import json
import random

from app.models import utcnow
from app.services.provider_types import ContentItemInput, TrendPointInput


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16)


def generate_github_history(target_ref: str, days: int = 45) -> list[TrendPointInput]:
    rng = random.Random(_seed(f"github:{target_ref}"))
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    baseline = rng.randint(18, 60)
    points: list[TrendPointInput] = []

    for offset in range(days):
        day = today - timedelta(days=days - offset - 1)
        wave = (offset % 7) * rng.uniform(0.8, 1.4)
        spike = rng.randint(10, 50) if offset in {days // 3, days // 2, days - 5} else 0
        value = baseline + wave + spike + rng.uniform(0, 6)
        points.append(
            TrendPointInput(
                source="github",
                metric="star_delta",
                source_type="backfill",
                bucket_granularity="day",
                bucket_start=day,
                value=round(value, 2),
                raw_json=json.dumps({"target_ref": target_ref, "synthetic": True, "offset": offset}),
            )
        )

    return points


def generate_github_content(target_ref: str, count: int = 6) -> list[ContentItemInput]:
    rng = random.Random(_seed(f"github-content:{target_ref}"))
    fetched_at = utcnow().replace(microsecond=0)
    content_types = ["release", "issue", "pull"]
    items: list[ContentItemInput] = []

    for index in range(count):
        content_type = content_types[index % len(content_types)]
        published_at = fetched_at - timedelta(hours=index * 9)
        title = f"{target_ref} {content_type} update #{index + 1}"
        items.append(
            ContentItemInput(
                source="github",
                source_type="backfill",
                external_key=f"{target_ref}:{content_type}:{index + 1}",
                title=title,
                url=f"https://github.com/{target_ref}/{content_type}/{index + 1}",
                summary=f"Deterministic mock {content_type} activity for {target_ref}. Seed {rng.randint(1000, 9999)}.",
                author="TrendScope Mock Provider",
                published_at=published_at,
                meta_json=json.dumps(
                    {
                        "content_type": content_type,
                        "rank": index + 1,
                        "fetched_at": fetched_at.isoformat(),
                        "synthetic": True,
                    }
                ),
            )
        )

    return items


def generate_newsnow_snapshot(query: str) -> tuple[list[TrendPointInput], list[ContentItemInput]]:
    rng = random.Random(_seed(f"newsnow:{query}"))
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    fetched_at = utcnow().replace(microsecond=0)

    platform_count = rng.randint(2, 6)
    item_count = rng.randint(4, 12)
    sources = ["weibo", "zhihu", "bilibili", "juejin", "36kr"]

    trend_points = [
        TrendPointInput(
            source="newsnow",
            metric="hot_hit_count",
            source_type="snapshot",
            bucket_granularity="day",
            bucket_start=today,
            value=float(item_count),
            raw_json=json.dumps({"query": query, "synthetic": True}),
        ),
        TrendPointInput(
            source="newsnow",
            metric="platform_count",
            source_type="snapshot",
            bucket_granularity="day",
            bucket_start=today,
            value=float(platform_count),
            raw_json=json.dumps({"query": query, "synthetic": True}),
        ),
    ]

    content_items: list[ContentItemInput] = []
    for index in range(item_count):
        source = sources[index % len(sources)]
        published_at = fetched_at - timedelta(hours=index * 3)
        title = f"{query} · synthetic signal #{index + 1}"
        content_items.append(
            ContentItemInput(
                source="newsnow",
                source_type="snapshot",
                external_key=f"{query}:{source}:{index + 1}",
                title=title,
                url=f"https://example.com/{source}/{index + 1}",
                summary=f"Deterministic mock content for {query} from {source}. Replace with a real provider later.",
                author="TrendScope Mock Provider",
                published_at=published_at,
                meta_json=json.dumps(
                    {
                        "platform": source,
                        "rank": index + 1,
                        "fetched_at": fetched_at.isoformat(),
                        "synthetic": True,
                    }
                ),
            )
        )
    return trend_points, content_items
