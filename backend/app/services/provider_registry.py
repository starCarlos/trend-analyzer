from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OnlineProviderSpec:
    source: str
    label: str
    smoke_blocking: bool = False


ONLINE_PROVIDER_SPECS = (
    OnlineProviderSpec(source="github", label="GitHub", smoke_blocking=True),
    OnlineProviderSpec(source="newsnow", label="NewsNow", smoke_blocking=True),
    OnlineProviderSpec(source="google_news", label="Google News"),
    OnlineProviderSpec(source="gdelt", label="GDELT"),
)

ONLINE_PROVIDER_SOURCES = tuple(spec.source for spec in ONLINE_PROVIDER_SPECS)
SMOKE_BLOCKING_PROVIDER_SOURCES = tuple(spec.source for spec in ONLINE_PROVIDER_SPECS if spec.smoke_blocking)


def iter_online_provider_specs() -> tuple[OnlineProviderSpec, ...]:
    return ONLINE_PROVIDER_SPECS


def get_online_provider_spec(source: str) -> OnlineProviderSpec | None:
    for spec in ONLINE_PROVIDER_SPECS:
        if spec.source == source:
            return spec
    return None
