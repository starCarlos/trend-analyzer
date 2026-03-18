from dataclasses import dataclass
import re


GITHUB_URL_RE = re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s]+?)(?:\.git|/)?$")
OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(slots=True)
class SearchTarget:
    raw_query: str
    normalized_query: str
    kind: str
    target_ref: str | None


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
