import signal
import time
from threading import Lock

from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import DuoModule, LogType
from .consumer import DuoLogsConsumer


class AdminLogsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 1000


class DuoAdminLogsConnector(Connector):
    module: DuoModule
    configuration: AdminLogsConnectorConfiguration

    LOGS_TO_FETCH = (LogType.AUTHENTICATION, LogType.ADMINISTRATION, LogType.TELEPHONY, LogType.OFFLINE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()
        self.consumers = {}

    def start_consumers(self):
        consumers = {}
        for log_type in self.LOGS_TO_FETCH:
            self.log(message=f"Start {log_type.name} consumer", level="info")
            consumers[log_type] = DuoLogsConsumer(connector=self, log_type=log_type)
            consumers[log_type].start()

        return consumers

    def supervise_consumers(self, consumers):
        for log_type, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting {log_type.name} consumer", level="info")

                consumers[log_type] = DuoLogsConsumer(connector=self, log_type=log_type)
                consumers[log_type].start()

    def stop_consumers(self, consumers):
        for name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping {name.name} consumer", level="info")
                consumer.stop()

    def run(self):
        consumers = self.start_consumers()

        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)
