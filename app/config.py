from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AthletiSync"
    app_secret_key: str = "change-me"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "sqlite:///./athletisync.db"
    timezone: str = "America/Chicago"
    scheduler_enabled: bool = True
    scheduler_timezone: str = "America/Chicago"

    default_admin_username: str = "admin"
    default_admin_password: str = "ChangeMe123!"

    mshsaa_base_url: str = "https://www.mshsaa.org"
    request_timeout_seconds: int = 20

    reverse_proxy_header: str = "X-Forwarded-Proto"

    @computed_field
    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()
