# flake8: noqa: E402
from datetime import datetime, timedelta

from sekoiaio.utils import should_patch

if should_patch():
    from gevent import monkey

    monkey.patch_all()

import json
from urllib.parse import urlparse

import requests
from sekoia_automation.trigger import Trigger
from websocket import WebSocketApp, WebSocketTimeoutException, setdefaulttimeout

from sekoiaio.triggers.messages_processor import MessagesProcessor
from sekoiaio.utils import user_agent


class _SEKOIANotificationBaseTrigger(Trigger):
    """Base code for all LiveAPI based triggers. This basically reads all
    notifications from LiveAPI through a WebSocket.

    This base class isn’t meant to be instanciated as directly, a
    subclass needs to be created with the proper handler
    defined. Subclass should define an `handle_xxx` method where `xxx`
    is the kind of event for which they want to trigger an event (for
    example, `handle_alert` or `handle_case`).

    This module relies on an APIKey authentication.

    """

    api_key: str

    seconds_without_events = 3600 * 24  # Force restart the pod every day if no events were received

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._message_processor: MessagesProcessor = MessagesProcessor(self.handler_dispatcher)
        self._websocket: WebSocketApp | None = None
        self._last_error: datetime | None = None
        self._last_close: datetime | None = None

    @property
    def liveapi_url(self):
        liveapi_url = self.module.configuration.get("liveapi_url")

        # LiveAPI URL might not be filled in existing playbooks. To
        # avoid having to edit all playbooks, infer the LiveAPI URL
        # from the base URL (which is mandatory).
        if liveapi_url is None:
            base_url = self.module.configuration["base_url"]
            domain = urlparse(base_url).netloc
            if domain in ["api.sekoia.io", "api.test.sekoia.io"]:
                domain = domain.replace("api", "app")

            liveapi_url = f"wss://{domain}/live/"

        return liveapi_url

    def run(self) -> None:
        self.log(f"Starting LiveAPI consumer on URL {self.liveapi_url}", level="info")

        api_key = self.module.configuration["api_key"]
        base_url = self.module.configuration["base_url"]

        # Ensure submitted APIKey is valid, raise a exception if not.
        response = requests.get(
            f"{base_url}/v1/me",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": user_agent()},
        )
        if response.status_code in [401, 403]:
            # Critical log will make the API stop the trigger deployment
            self.log("The credential provided are invalid", level="critical")
            self._error_count = 5  # Set the number of error to the maximum so the pod exits directly
        response.raise_for_status()

        self._message_processor.start()

        setdefaulttimeout(10)  # socket timeout
        self._websocket = WebSocketApp(
            self.liveapi_url,
            on_message=self.on_message,
            on_close=self.on_close,
            on_error=self.on_error,
            on_ping=self.on_ping,
            on_pong=self.on_pong,
            cookie=f"access_token_cookie={api_key}",
        )
        self.log("Websocket starts listening", level="info")
        while self.running:
            try:
                self._websocket.run_forever(ping_interval=20, ping_timeout=5)
            except WebSocketTimeoutException:
                self.log("The websocket timed out", level="error")

    def on_error(self, _, error: Exception):
        now = datetime.utcnow()
        if self._last_error and now < self._last_error + timedelta(seconds=10):
            # Prevent from sending too many exceptions
            return
        self._last_error = now
        self.log_exception(
            exception=error,
            message="An exception occurred in the main WebSocket client’s loop",
        )

    def on_ping(self, _, __):
        self.log("Responded to ping sent by server", level="debug")

    def on_pong(self, _, __):
        self.log("Received pong from server", level="debug")

    def on_close(self, *args, **kwargs):  # pragma: no cover
        # Reset teardown so we can run again the app from the start
        with self._websocket.has_done_teardown_lock:
            self._websocket.has_done_teardown = False
        now = datetime.utcnow()
        if self._last_close and now < self._last_close + timedelta(seconds=10):
            # Prevent from sending too many logs
            return
        self._last_close = now
        self.log("Socket closed", level="warning")

    def on_message(self, _, raw_message: str):
        self._message_processor.push_message(raw_message)

    def handler_dispatcher(self, raw_message: str):
        """Dispatch events to handler methods given the event type.

        This method will load JSON messages and then forward message
        (as dict) to `handle_${event_type}` method.

        """
        try:
            message = json.loads(raw_message)
        except Exception:
            self.log("Invalid JSON message received from LiveAPI", level="error")
            return

        # We can only manage v1 events
        if str(message.get("event_version")) != "1":
            self.log("Invalid event version", level="error", event=message)
            return

        event_type = message.get("event_type")

        # We don’t know how to handle such messages.
        if event_type is None:
            self.log("Empty event type", level="error", event=message)
            return

        try:
            handler = getattr(self, f"handle_{event_type}")
            handler(message)
        except AttributeError:
            return

    def stop(self, *args, **kwargs):
        super().stop(*args, **kwargs)
        self._message_processor.stop()
        if self._websocket:
            self._websocket.close()
