import time
import uuid
import zipfile
from io import BytesIO

import orjson
import requests
from sekoia_automation.trigger import Trigger


class FetchTrancoListTrigger(Trigger):
    top_domains_url = "https://tranco-list.eu/top-1m.csv.zip"

    @property
    def chunk_size(self):
        return self.configuration.get("chunk_size", 10000)

    @property
    def interval(self):
        return self.configuration.get("interval", 24) * 3600

    def run(self):
        self.log("Trigger starting")
        try:
            while True:
                self._run()
        finally:
            self.log("Trigger stopping")

    def _run(self):
        self.log("Starting run")
        domains = self.get_top_domains()
        if not domains:
            return
        created_events = 0
        for chunk, offset in self.domain_chunks(domains):
            self.create_event_for_chunk(chunk, offset)
            created_events += 1
        self.log(f"Pushed {created_events} chunk events")
        self.log(f"Sleeping for {self.interval} seconds", level="debug")
        time.sleep(self.interval)

    def create_event_for_chunk(self, chunk, offset):
        chunk_size = min(self.chunk_size, len(chunk))
        work_dir = self._data_path.joinpath("tranco_chunks").joinpath(str(uuid.uuid4()))
        chunk_path = work_dir.joinpath("observables.json")
        work_dir.mkdir(parents=True, exist_ok=True)
        with chunk_path.open("w") as fp:
            fp.write(orjson.dumps(chunk).decode("utf-8"))

        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(chunk_path.relative_to(work_dir))
        self.send_event(
            event_name=f"Tranco List Chunk {offset}-{offset+chunk_size}",
            event=dict(file_path=file_path, chunk_offset=offset, chunk_size=chunk_size),
            directory=directory,
            remove_directory=True,
        )

    def get_top_domains(self) -> list:
        response = requests.get(self.top_domains_url, stream=True)
        if not response.ok:
            self.log(f"Server answered with {response.status_code}", level="error")
            return []
        with zipfile.ZipFile(BytesIO(response.content)) as zp:
            with zp.open("top-1m.csv") as fp:
                # Can't use any generator/iterator since they are not subscriptable
                return [line.decode("utf-8").split(",")[1].strip() for line in fp.readlines()]

    def domain_chunks(self, domains):
        for i in range(0, len(domains), self.chunk_size):
            yield domains[i : i + self.chunk_size], i
