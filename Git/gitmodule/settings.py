from functools import lru_cache
from pathlib import Path

from pydantic import BaseSettings


class Settings(BaseSettings):
    module_directory: Path = Path("/tmp/gitmodule")
    repository_directory: str = "repository"

    class Config:
        env_prefix = "symphony_git_"


@lru_cache
def get_settings():
    return Settings()
