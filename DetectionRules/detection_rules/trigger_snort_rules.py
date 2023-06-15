import os
import uuid

import orjson
from apscheduler.schedulers.blocking import BlockingScheduler
from sekoia_automation.trigger import Trigger

from detection_rules.cache import Cache
from detection_rules.fetcher import RulesFetcher


class SnortRulesTrigger(Trigger):
    def run(self) -> None:
        try:
            self._schedule()
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            if self._scheduler.running:
                self._scheduler.shutdown()

    def _schedule(self) -> None:
        self._scheduler = BlockingScheduler()
        frequency = 3600 * 24  # run once a day
        self._scheduler.add_job(
            self._run,
            kwargs={"archives": self.configuration["archives"]},
            trigger="interval",
            seconds=frequency,
        )

    def _run(self, archives) -> None:
        cache = Cache(os.environ.get("CACHE_DIR", "/data"))
        rules = RulesFetcher(archives, cache).fetch_rules()
        if not rules:
            return
        bundle = {
            "type": "bundle",
            "id": f"bundle--{str(uuid.uuid4())}",
            "objects": rules,
        }

        # Save bundle in file
        work_dir = self._data_path.joinpath("snort_rules").joinpath(str(uuid.uuid4()))
        work_dir.mkdir(parents=True, exist_ok=True)

        rule_path = work_dir.joinpath("rules.json")
        with rule_path.open("w") as fp:
            fp.write(orjson.dumps(bundle).decode("utf-8"))

        # Send event
        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(rule_path.relative_to(work_dir))
        self.send_event(
            event_name="SNORT rules",
            event=dict(bundle_path=file_path),
            directory=directory,
            remove_directory=True,
        )
