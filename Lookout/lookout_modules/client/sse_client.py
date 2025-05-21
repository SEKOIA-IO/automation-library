import logging
from typing import Generator

import requests

from .server_sent_event import SSEvent

SSE_DELIMITER = (b"\r\r", b"\n\n", b"\r\n\r\n")
SSE_FIELD_SEP = ":"
SSE_DEFAULT_TIMEOUT = 5  # seconds

logger = logging.getLogger(__name__)


class SSEClient:
    """
    Python Server Sent Event client for streaming events from an SSE server,
    based on the HTML spec for Server Sent Events.

    Specification: https://html.spec.whatwg.org/multipage/server-sent-events.html#server-sent-events
    """

    def __init__(self, event_stream: requests.Response, event_enc: str = "utf-8"):
        self.event_stream = event_stream
        self.event_enc = event_enc

    def __read(self) -> Generator[bytes, None, None]:
        """
        Read from the event stream and yield raw event data.

        Yields:
            bytes: Raw event bytes
        """
        raw_event = b""
        # NOTE: requests.Response.__iter__() uses request.Response.iter_content(128)
        for event_part in self.event_stream:
            # NOTE: splitlines(True) splits the line, but preserves the line ending character(s)
            #   Is necessary so we can parse the SSE delimiter.
            for line in event_part.splitlines(True):
                raw_event += line
                if raw_event.endswith(SSE_DELIMITER):
                    yield raw_event
                    raw_event = b""

        # Yield any trailing bytes if the stream ended without a delimiter
        if raw_event:
            yield raw_event

    def iter_stream_events(self) -> Generator[SSEvent, None, None]:
        """
        Stream events from a SSE endpoint

        Yields:
            SSEvent: Server Sent Event
        """
        for raw_event in self.__read():
            event = SSEvent()
            for encoded_line in raw_event.splitlines():
                line = encoded_line.decode(self.event_enc)
                # NOTE: Spec states:
                #   If the line is empty (a blank line), Dispatch the event, as defined below.
                #   If the line starts with a U+003A COLON character (:), Ignore the line.
                if not line.strip() or line.startswith(SSE_FIELD_SEP) or (SSE_FIELD_SEP not in line):
                    continue

                # NOTE: line is '<field_name>: <value>'
                #   only split once to preserve `:` characters in value
                (field, value) = line.split(SSE_FIELD_SEP, 1)
                try:
                    event.append(field, value.strip())
                except ValueError as e:
                    logger.warning(str(e))

            # remove the last newline appended to data section
            event.data = event.data.strip()

            if not event.blank():
                yield event

        self.close()

    def close(self) -> None:
        """
        Close the event stream.
        """
        self.event_stream.close()
