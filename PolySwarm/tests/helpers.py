"""Mocks that fail when the module calls something the PolySwarm library does not have.

A bare MagicMock answers to any attribute and takes any arguments, so a test
can pass while asserting on a method the library never shipped. Both helpers
here are specced against the real client, so a misspelled method or a wrong
keyword fails at the call site instead.
"""

from unittest.mock import MagicMock, create_autospec

from polyswarm_api import settings
from polyswarm_api.api import PolyswarmAPI
from polyswarm_api.core import PolyswarmRequest, PolyswarmSession

from polyswarm_modules.client import build_client


def autospec_api() -> MagicMock:
    """A stand-in for a PolyswarmAPI instance, limited to the real client's surface."""
    api = create_autospec(PolyswarmAPI, instance=True)
    # Set in the library's __init__, so a spec built from the class cannot see them.
    api.uri = settings.DEFAULT_GLOBAL_API
    api.community = settings.DEFAULT_COMMUNITY
    api.timeout = settings.DEFAULT_HTTP_TIMEOUT
    api.session = create_autospec(PolyswarmSession, instance=True)
    return api


def autospec_build_client() -> MagicMock:
    """A stand-in for build_client that checks its own arguments and hands back a specced client.

    Used as new_callable so every test gets a fresh client, since an instance
    built once at import time would carry call history from one test to the next.
    """
    factory = create_autospec(build_client)
    factory.return_value = autospec_api()
    return factory


def autospec_request(status_code: int | None = None) -> MagicMock:
    """A stand-in for the request the library attaches to its own exceptions.

    The status code is an attribute the library sets in __init__, so it is
    added here rather than found on the class.
    """
    request = create_autospec(PolyswarmRequest, instance=True)
    if status_code is not None:
        request.status_code = status_code
    return request
