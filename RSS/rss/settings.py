from functools import lru_cache
from pathlib import Path

from pydantic import BaseSettings


class Settings(BaseSettings):
    cache_dir: Path = Path("/var/cache/symphony_rss_module")

    class Config:
        env_prefix = "symphony_rss_"


@lru_cache
def get_settings():
    return Settings()
