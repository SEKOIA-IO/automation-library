import time

from sekoia_automation.trigger import Trigger

from gitmodule.repository import GitRepository


class GitTrigger(Trigger):
    """
    Trigger that works by regularily updating a Git Repository
    """

    @property
    def sleep_time(self):
        return self.configuration.get("sleep_time", 300)

    def run(self):
        self.log("Trigger is starting")
        self._init_repository()

        while True:
            self._run()
            time.sleep(self.sleep_time)

    def _init_repository(self):
        self._repository = GitRepository(self.module.configuration["repository_url"], data_path=self._data_path)
        self._repository.clone()
        self._last_commit = self._repository.last_commit().hexsha

    def _new_commit(self):
        self._repository.pull()
        last_commit = self._repository.last_commit().hexsha

        if last_commit != self._last_commit:
            return last_commit

        return None

    # Should be defined by subclasses with the event creation logic
    def _run(self):
        raise NotImplementedError
