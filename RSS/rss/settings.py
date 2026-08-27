from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="symphony_rss_")

    cache_dir: Path = Path("/var/cache/symphony_rss_module")


@lru_cache
def get_settings():
    return Settings()
