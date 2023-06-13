from gitmodule.settings import get_settings

from .base import GitTrigger


class NewCommitTrigger(GitTrigger):
    """
    Trigger that gets the new Git Commits on a regular basis
    """

    def _run(self):
        new_commit = self._new_commit()

        # See if there was any changes
        if new_commit:
            for commit in self._repository.iter_commits():
                if commit.hexsha == self._last_commit:
                    break

                commit_data = {
                    "commit": {
                        "hexsha": commit.hexsha,
                        "summary": commit.summary,
                        "message": commit.message,
                        "datetime": commit.committed_date,
                        "author_name": commit.author.name,
                        "author_email": commit.author.email,
                    },
                    "repository_path": get_settings().repository_directory,
                }
                self.log(f"Got new commit {commit.summary}")
                self.send_event(
                    f"Commit: {commit.summary}",
                    commit_data,
                    get_settings().repository_directory,
                )

            self._last_commit = new_commit
