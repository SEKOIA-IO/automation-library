from pathlib import Path

import git

from gitmodule.settings import get_settings
from gitmodule.utils import copytree


class GitRepository:
    def __init__(self, url, data_path: Path | None = None):
        self._url = url
        self.name = self._get_repo_name()
        self.path = self._get_repository_dir(self.name)
        self._data_path = data_path

    def _get_repository_dir(self, name) -> Path:
        base = Path(get_settings().module_directory) / get_settings().repository_directory
        base.mkdir(parents=True, exist_ok=True)
        return base / name

    def _get_repo_name(self):
        name = self._url.split("/")[-1]

        if name.endswith(".git"):
            name = name[:-4]

        return name

    def clone(self) -> bool:
        """
        Clone the repository

        Return True if the repository was cloned, False if it already existed"""
        if (self.path / ".git").is_dir():
            self._repo = git.Repo(self.path.as_posix())
            return False

        if self._data_path and (self._data_path / get_settings().repository_directory / ".git").is_dir():
            copytree(self._data_path / get_settings().repository_directory, self.path)
            self._repo = git.Repo(self.path.as_posix())
            return False
        else:
            self._repo = git.Repo.clone_from(self._url, self.path.as_posix())
            if self._data_path:
                copytree(self.path, self._data_path / get_settings().repository_directory)
            return True

    def pull(self):
        self._repo.remotes.origin.pull()
        if self._data_path:
            copytree(self.path, self._data_path / get_settings().repository_directory)

    def last_commit(self):
        return self._repo.active_branch.commit

    def __getattr__(self, name):
        return getattr(self._repo, name)
