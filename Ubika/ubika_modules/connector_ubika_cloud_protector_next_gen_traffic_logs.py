from datetime import datetime

import orjson

from ubika_modules.client.auth import AuthorizationError, AuthorizationTimeoutError

from .connector_ubika_cloud_protector_next_gen_base import (
    UbikaCloudProtectorNextGenBaseConnector,
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)


class UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration(
    UbikaCloudProtectorNextGenBaseConnectorConfiguration
):
    pass


class UbikaCloudProtectorNextGenTrafficLogsConnector(UbikaCloudProtectorNextGenBaseConnector):
    """
    Connector that continuously polls the Ubika Cloud Protector NextGen
    traffic-logs endpoint and forwards them to the configured intake.
    Uses TimeStepper to manage time ranges.
    """

    NAME: str = "Ubika Cloud Protector NextGen Traffic Logs"
    configuration: UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration

    def next_batch(self, start: datetime, end: datetime) -> None:
        """
        Fetch pages for the given time range, serialize and push events to intake.
        Updates the checkpoint with the end time.
        """
        start_timestamp = int(start.timestamp() * 1000)
        end_timestamp = int(end.timestamp() * 1000)

        # Fetch all pages for this time range
        for events in self._get_pages(
            endpoint="traffic-logs",
            params={
                "filters.fromDate": start_timestamp,
                "filters.toDate": end_timestamp,
                "pagination.pageSize": self.configuration.chunk_size,
                "pagination.realtime": True,
            },
        ):
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is not empty, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} traffic-log events to the intake",
                    level="info",
                )
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # Update checkpoint with the end time of this batch
        with self.context as cache:
            cache["most_recent_date_seen"] = end.isoformat()

    def run(self) -> None:
        """
        Main loop using TimeStepper to manage time ranges:
        1) Use stepper.ranges() to get successive time windows
        2) For each window, call next_batch() to fetch and push events
        3) Stepper manages sleep timing and lag handling
        """
        self.log(message=f"Start fetching {self.NAME} events", level="info")

        try:
            for start, end in self.stepper.ranges():
                # Check if we need to stop
                if self._stop_event.is_set():
                    break

                try:
                    self.next_batch(start, end)
                except (AuthorizationError, AuthorizationTimeoutError):
                    # Let authorization errors bubble up to trigger connector disablement and alerting
                    raise
                except Exception as error:
                    self.log_exception(error, message="Error fetching traffic logs")
                    break

        finally:
            # Cleanup on stop or fatal error
            self.client.close()
            self.log(message=f"Stopped fetching {self.NAME} events", level="info")
