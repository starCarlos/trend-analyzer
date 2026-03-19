from __future__ import annotations

from dataclasses import dataclass
import re


EXTRA_FEED_SPLIT_RE = re.compile(r"[\n;,]+")
NON_SLUG_CHAR_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class DirectRssFeedSpec:
    source_id: str
    label: str
    url: str
    language: str = "any"


DIRECT_RSS_FEEDS = (
    DirectRssFeedSpec(
        source_id="36kr",
        label="36Kr",
        url="https://36kr.com/feed",
        language="zh",
    ),
    DirectRssFeedSpec(
        source_id="sspai",
        label="SSPAI",
        url="https://sspai.com/feed",
        language="zh",
    ),
    DirectRssFeedSpec(
        source_id="ithome",
        label="IT Home",
        url="https://www.ithome.com/rss/",
        language="zh",
    ),
    DirectRssFeedSpec(
        source_id="leiphone",
        label="Leiphone",
        url="https://www.leiphone.com/feed",
        language="zh",
    ),
    DirectRssFeedSpec(
        source_id="techcrunch",
        label="TechCrunch",
        url="https://techcrunch.com/feed/",
        language="en",
    ),
    DirectRssFeedSpec(
        source_id="infoq",
        label="InfoQ",
        url="https://feed.infoq.com/",
        language="en",
    ),
    DirectRssFeedSpec(
        source_id="the_verge",
        label="The Verge",
        url="https://www.theverge.com/rss/index.xml",
        language="en",
    ),
    DirectRssFeedSpec(
        source_id="ars_technica",
        label="Ars Technica",
        url="https://feeds.arstechnica.com/arstechnica/index",
        language="en",
    ),
)


def _slugify_label(label: str) -> str:
    slug = NON_SLUG_CHAR_RE.sub("_", label.strip().casefold()).strip("_")
    return slug or "custom_feed"


def _parse_extra_direct_rss_feeds(raw: str) -> tuple[DirectRssFeedSpec, ...]:
    feeds: list[DirectRssFeedSpec] = []
    seen_urls: set[str] = set()
    for chunk in EXTRA_FEED_SPLIT_RE.split(raw.strip()):
        entry = chunk.strip()
        if not entry or "|" not in entry:
            continue
        label, url = (part.strip() for part in entry.split("|", 1))
        if not label or not url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        feeds.append(
            DirectRssFeedSpec(
                source_id=_slugify_label(label),
                label=label,
                url=url,
            )
        )
    return tuple(feeds)


def iter_direct_rss_feeds(extra_feeds: str = "") -> tuple[DirectRssFeedSpec, ...]:
    if not extra_feeds.strip():
        return DIRECT_RSS_FEEDS

    resolved: list[DirectRssFeedSpec] = []
    seen_urls: set[str] = set()
    for feed in DIRECT_RSS_FEEDS + _parse_extra_direct_rss_feeds(extra_feeds):
        if feed.url in seen_urls:
            continue
        seen_urls.add(feed.url)
        resolved.append(feed)
    return tuple(resolved)
