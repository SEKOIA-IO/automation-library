from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest
import requests
import urllib3


@pytest.fixture(
    params=[
        pytest.param(None, id="no-error"),
        pytest.param(requests.HTTPError("http error"), id="requests-http-error"),
        pytest.param(urllib3.exceptions.HTTPError("urllib3 error"), id="urllib3-http-error"),
    ]
)
def recoverable_error(request: pytest.FixtureRequest) -> Exception | None:
    """Errors a trigger loop logs before going on with the next cycle."""
    return request.param


@pytest.fixture
def run_one_cycle() -> Callable[..., Mock]:
    """Run the loop of a trigger for a single cycle: its step stops the trigger, then optionally raises."""

    def _run(trigger: Any, step_name: str, error: BaseException | None = None, frequency: int = 60) -> Mock:
        trigger.configuration.frequency = frequency
        trigger.authentication = Mock()

        def step(*args: Any, **kwargs: Any) -> None:
            trigger._stop_event.set()
            if error is not None:
                raise error

        step_mock = Mock(side_effect=step)
        setattr(trigger, step_name, step_mock)
        trigger.run()
        return step_mock

    return _run
