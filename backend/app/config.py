from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TrendScope API"
    app_env: str = "development"
    database_url: str = "sqlite:///./trendscope.db"
    frontend_origin: str = "http://127.0.0.1:5081"
    scheduler_enabled: bool = False
    scheduler_interval_seconds: int = 1800
    scheduler_initial_delay_seconds: int = 15
    scheduler_period: str = "30d"
    scheduler_run_backfill_now: bool = True
    provider_mode: str = "mock"
    github_token: str = ""
    github_api_base_url: str = "https://api.github.com"
    github_history_max_pages: int = 10
    newsnow_base_url: str = "https://newsnow.busiyi.world"
    newsnow_source_ids: str = "weibo,zhihu,bilibili,juejin,36kr,github"
    google_news_enabled: bool = True
    google_news_history_days: int = 365
    google_news_max_items: int = 80
    gdelt_enabled: bool = True
    gdelt_history_days: int = 90
    gdelt_max_items: int = 80
    request_timeout_seconds: float = 8.0
    http_proxy: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
