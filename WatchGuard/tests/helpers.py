from typing import Any

import aiohttp
from aioresponses import CallbackResult


def aioresponses_callback(
    response_payload: dict[str, Any] | None = None,
    auth: aiohttp.BasicAuth | None = None,
    headers: dict[str, str] | None = None,
    status: int = 200,
):
    """
    Callback function for aioresponses to handle requests.
    """

    def _check(url, **kwargs):
        if auth:
            assert kwargs["auth"] == auth, "Authentication headers do not match"

        if headers:
            for key, value in headers.items():
                assert kwargs["headers"].get(key) == value, f"Header {key} does not match"

        return CallbackResult(status=status, payload=response_payload)

    return _check
