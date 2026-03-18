from dataclasses import dataclass
import re
from typing import Callable


GITHUB_URL_RE = re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s]+?)(?:\.git|/)?$")
OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BARE_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(slots=True)
class SearchTarget:
    raw_query: str
    normalized_query: str
    kind: str
    target_ref: str | None


RepoLookup = Callable[[str], str | None]


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_search_query(raw_query: str) -> SearchTarget:
    cleaned = _normalize_spaces(raw_query)
    if not cleaned:
        raise ValueError("Search query cannot be empty.")

    github_match = GITHUB_URL_RE.match(cleaned)
    if github_match:
        owner, repo = github_match.groups()
        target_ref = f"{owner.lower()}/{repo.lower()}"
        return SearchTarget(
            raw_query=cleaned,
            normalized_query=target_ref,
            kind="github_repo",
            target_ref=target_ref,
        )

    if OWNER_REPO_RE.match(cleaned):
        target_ref = cleaned.lower()
        return SearchTarget(
            raw_query=cleaned,
            normalized_query=target_ref,
            kind="github_repo",
            target_ref=target_ref,
        )

    normalized = cleaned.lower()
    return SearchTarget(
        raw_query=cleaned,
        normalized_query=normalized,
        kind="keyword",
        target_ref=None,
    )


def should_attempt_repo_resolution(value: str) -> bool:
    return bool(BARE_REPO_RE.match(value)) and bool(re.search(r"[A-Za-z]", value))


def resolve_search_query(raw_query: str, *, repo_lookup: RepoLookup | None = None) -> SearchTarget:
    target = parse_search_query(raw_query)
    if target.kind != "keyword" or repo_lookup is None or not should_attempt_repo_resolution(target.raw_query):
        return target

    resolved_repo = repo_lookup(target.raw_query)
    if not resolved_repo:
        return target

    normalized_repo = resolved_repo.strip().lower()
    if not OWNER_REPO_RE.match(normalized_repo):
        return target

    return SearchTarget(
        raw_query=target.raw_query,
        normalized_query=normalized_repo,
        kind="github_repo",
        target_ref=normalized_repo,
    )
