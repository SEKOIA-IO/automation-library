from queue import Queue
from threading import Event, Thread
from typing import Callable

from websocket import WebSocketApp, WebSocketTimeoutException

from retarus_modules.configuration import RetarusConfig


class RetarusEventsConsumer(Thread):
    """Handler for receiving events from a websocket"""

    def __init__(
        self,
        configuration: RetarusConfig,
        queue: Queue,
        logger: Callable,
        logger_exception: Callable,
    ):
        super().__init__()
        self.queue = queue
        self.configuration = configuration
        self.log = logger
        self.log_exception = logger_exception

        # Event used to stop the thread
        self._stop_event = Event()

    def stop(self):
        """Sets the stop event"""
        self._stop_event.set()

        # close the websocket
        if self.websocket:
            self.websocket.close()

    def create_websocket(self) -> WebSocketApp:
        """Creates a WebSocket inside a Thread

        Return:
            WebSocketApp: The websocket we opened
        """
        return WebSocketApp(
            url=self.configuration.ws_url,
            header=[f"Authorization: Bearer {self.configuration.ws_key}"],
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

    def on_message(self, _, event: str) -> None:
        """Callback method called when the websocket receives a message

        It will send the received message to the queue for consumption by the forwarder

        Args:
            _ (_type_): _description_
            event (str): Message received on the websocket
        """
        self.queue.put(event)

    def on_error(self, _, error: Exception):
        """Callback method called when the websocket encounters an exception

        We log the exception using the Connector's logger, as a warning if it is a timeout, as an error otherwise

        Args:
            _ (_type_): _description_
            error (Exception): Exception encountered
        """
        if isinstance(error, WebSocketTimeoutException):
            # add a gentler message for timeout
            self.log(message="Websocket timed out", level="warning")
        else:
            self.log(message=f"Websocket error: {error}", level="error")

    def on_close(self, *_):
        """Callback method called when the websocket is closed"""
        self.log(message="Closing socket connection", level="info")

    def run(self):
        """Start the websocket thread then wait for the stop event to be set and close the websocket when it happens"""
        self.log(message=f"Connection to stream {self.configuration.ws_url}", level="info")
        while self.is_running:
            self.websocket = self.create_websocket()
            teardown = self.websocket.run_forever()

            # The worker is stopping, exit here
            if not self.is_running:
                return

            if not teardown:
                self.log("Websocket event loop stopped for an unknown reason", level="error")

            self.log("Failure in the websocket event loop", level="warning")

    @property
    def is_running(self) -> bool:
        """Helper method to check if the stop event has been set

        Returns:
            bool: False if _stop_event is set, True otherwise
        """
        return not self._stop_event.is_set()
