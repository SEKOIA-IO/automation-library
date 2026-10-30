from requests import Response

from polyswarm_modules.client import failure_kind, status_of


def _response(status: int) -> Response:
    response = Response()
    response.status_code = status
    return response


def test_status_of_reads_the_response() -> None:
    exc = RuntimeError("boom")
    exc.response = _response(429)  # type: ignore[attr-defined]

    assert status_of(exc) == 429
    assert failure_kind(exc) == "RuntimeError, HTTP 429"


def test_status_of_reads_the_request_when_there_is_no_response() -> None:
    exc = RuntimeError("boom")
    exc.request = _response(401)  # type: ignore[attr-defined]

    assert status_of(exc) == 401


def test_status_of_is_none_when_nothing_carries_a_status() -> None:
    exc = RuntimeError("boom")

    assert status_of(exc) is None
    assert failure_kind(exc) == "RuntimeError"
