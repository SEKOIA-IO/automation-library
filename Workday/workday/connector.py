import time
from threading import Lock
from pathlib import Path
from sekoia_automation.connector import Connector

from .endpoint import WorkdayEndpoint
from . import WorkdayModule
from .client import WorkdayApiClient

class WorkdayConnector(Connector):
    module: WorkdayModule
    FEATURE_TO_CLASS = {WorkdayEndpoint.FEATURE_NAME: WorkdayEndpoint}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context_lock = Lock()
        self._data_path = Path(self.module.configuration.data_path) if hasattr(self.module.configuration, "data_path") else self.data_path

        # validate credentials
        WorkdayApiClient(
            token_endpoint=self.module.configuration.token_endpoint,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            refresh_token=self.module.configuration.refresh_token,
            workday_host=self.module.configuration.workday_host,
        ).get_access_token()

    @property
    def data_path(self):
        return self._data_path

    def start_consumers(self):
        consumers = {}
        for name, cls in self.FEATURE_TO_CLASS.items():
            self.log(message=f"Starting {name}", level="info")
            consumers[name] = cls(connector=self)
            consumers[name].start()
        return consumers

    def stop_consumers(self, consumers):
        for consumer in consumers.values():
            if consumer.is_alive():
                consumer.stop()
                consumer.join(timeout=10)

    def supervise_consumers(self, consumers):
        for name, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                cls = self.FEATURE_TO_CLASS[name]
                consumers[name] = cls(connector=self)
                consumers[name].start()

    def run(self):
        consumers = self.start_consumers()
        try:
            while self.running:
                self.supervise_consumers(consumers)
                time.sleep(5)
        finally:
            self.stop_consumers(consumers)
