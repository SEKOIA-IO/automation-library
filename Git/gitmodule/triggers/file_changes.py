import os
import shutil
import uuid
from fnmatch import fnmatch

from gitmodule.repository import GitRepository
from gitmodule.settings import get_settings
from gitmodule.triggers.base import GitTrigger
from gitmodule.utils import copytree


def filechanges_directory():
    return os.path.join(get_settings().repository_directory, "file_changes")


def safe_join(base_path, *parts):
    computed_path = base_path.joinpath(*parts)

    if not os.path.normpath(computed_path.as_posix()).startswith(base_path.as_posix()):
        raise ValueError(f"Path {computed_path} is invalid")

    return computed_path


class FileChangesTrigger(GitTrigger):
    """
    Trigger that gets the file changes on a regular basis
    """

    @property
    def chunk_size(self):
        """Get Chunk Size from configuration (None by default)"""
        return self.configuration.get("chunk_size")

    @property
    def file_filter(self):
        """Get fnmatch file filter to apply to changes"""
        return self.configuration.get("filter", "*")

    @property
    def send_initial_state(self):
        """Send existing files when first cloning the repository"""
        return self.configuration.get("send_initial_state", False) in [True, "True"]

    @property
    def include_repository(self):
        """Include whole repository with every event"""
        return self.configuration.get("include_repository", True) in [True, "True"]

    def _init_repository(self):
        self._repository = GitRepository(self.module.configuration["repository_url"])
        was_cloned = self._repository.clone()
        self._last_commit = self._repository.last_commit().hexsha

        if self.send_initial_state and was_cloned:
            changes = []

            for item in self._repository.head.commit.tree.traverse():
                if item.type == "blob":
                    changes.append({"filepath": item.path, "change_type": "A"})

            self._send_changes(changes, self._last_commit)

    def file_changes(self, new_commit):
        changes = []
        old_commit = self._repository.commit(self._last_commit)

        for file_change in old_commit.diff(new_commit):
            changes.append({"filepath": file_change.b_path, "change_type": file_change.change_type})

        return changes

    def file_changes_chunks(self, changes):
        # If no chunk_size was specified, do not chunk file changes
        if self.chunk_size is None:
            yield changes
        else:
            for i in range(0, len(changes), self.chunk_size):
                yield changes[i : i + self.chunk_size]

    def filter_changes(self, changes):
        filtered_changes = []

        for change in changes:
            if fnmatch(change["filepath"], self.file_filter):
                filtered_changes.append(change)

        return filtered_changes

    def _run(self):
        new_commit = self._new_commit()

        # See if there was any changes
        if new_commit:
            changes = self.file_changes(new_commit)
            self._send_changes(changes, new_commit)

            self._last_commit = new_commit

    def _send_changes(self, changes, new_commit):
        changes = self.filter_changes(changes)

        if changes:
            for chunk in self.file_changes_chunks(changes):
                event = {
                    "changes": chunk,
                    "new_commit": new_commit,
                    "old_commit": self._last_commit,
                }

                if self.include_repository:
                    workdir = self._data_path / get_settings().repository_directory
                    copytree(self._repository.path, workdir)
                    remove_directory = False
                    event["repository_path"] = self._repository.name
                else:
                    workdir = self._data_path / filechanges_directory() / str(uuid.uuid4())
                    self._create_filechanges_directory(workdir, chunk)
                    remove_directory = True

                self.log(f"Got {len(chunk)} file changes")
                directory = str(workdir.relative_to(self._data_path))
                self.send_event(
                    f"{len(chunk)} file changes",
                    event,
                    directory,
                    remove_directory=remove_directory,
                )

    def _create_filechanges_directory(self, directory, changes):
        filechanges_path = directory

        for change in changes:
            srcpath = safe_join(self._repository.path, change["filepath"])

            if os.path.isfile(srcpath):
                dstpath = safe_join(filechanges_path, change["filepath"])

                # Make sure directory exists
                dstpath.parent.mkdir(parents=True, exist_ok=True)

                # Copy the file
                with srcpath.open("rb") as srcf, dstpath.open("wb") as dstf:
                    shutil.copyfileobj(srcf, dstf)
