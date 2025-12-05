# flake8: noqa: E402
import os
from datetime import datetime, timedelta
from posixpath import join as urljoin

from tenacity import Retrying, wait_exponential, stop_after_attempt

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
    last_heartbeat_threshold = 600  # Force restart the pod if no heartbeat was received for 10 minutes

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

    @property
    def ssl_opt(self) -> dict[str, str]:
        """
        Return the SSL options to use for the WebSocket connection. See
        https://websocket-client.readthedocs.io/en/latest/faq.html#what-else-can-i-do-with-sslopts
        """
        ca_certs = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("CURL_CA_BUNDLE")
        if ca_certs:
            return {"ca_certs": ca_certs}
        return {}

    def run(self) -> None:
        self.log(f"Starting LiveAPI consumer on URL {self.liveapi_url}", level="info")

        api_key = self.module.configuration["api_key"]
        base_url = self.module.configuration["base_url"]

        self.log(f"Base URL provided is {base_url}", level="info")

        self._validate_api_key(base_url, api_key)

        if not self._message_processor.is_alive():
            self._message_processor.start()

        setdefaulttimeout(10)  # socket timeout
        self._websocket = WebSocketApp(
            self.liveapi_url,
            on_open=self.on_open,
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
                self._websocket.run_forever(ping_interval=20, ping_timeout=5, sslopt=self.ssl_opt)
            except WebSocketTimeoutException:
                self.log("The websocket timed out", level="error")

    def on_open(self, ws):
        # Ask `liveapi` to push v1 and v2 notifications.
        ws.send('{"action": "upgrade"}')

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
        self.heartbeat()

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
        self.heartbeat()
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

        if message.get("authenticated"):
            # Ignore auth messages
            return

        # We can only manage v2 events
        if str(message.get("metadata", {}).get("version")) != "2":
            self.log("Received event with version not handled by the trigger", level="info", event=message)
            return

        event_type = message.get("type")

        # We don’t know how to handle such messages.
        if event_type is None:
            self.log("Empty event type", level="error", event=message)
            return

        self.handle_event(message)

    def stop(self, *args, **kwargs):
        super().stop(*args, **kwargs)
        self._message_processor.stop()
        if self._websocket:
            self._websocket.close()

    def _validate_api_key(self, base_url: str, api_key: str):
        """Ensure submitted APIKey is valid, raise a exception if not."""
        url = urljoin(base_url, "api/v1/me").replace("/api/api", "/api")  # In case base_url ends with /api
        for attempt in Retrying(
            reraise=True,
            wait=wait_exponential(max=10),
            stop=stop_after_attempt(10),
        ):
            with attempt:
                response = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}", "User-Agent": user_agent()},
                )
                # Retry 5xx errors
                if response.status_code >= 500:
                    response.raise_for_status()
        if response.status_code in [401, 403]:
            # Critical log will make the API stop the trigger deployment
            self.log("The credential provided are invalid", level="critical")
            self._error_count = 5  # Set the number of error to the maximum so the pod exits directly
        response.raise_for_status()
