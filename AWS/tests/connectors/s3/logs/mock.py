from collections.abc import Callable
from contextlib import contextmanager
from unittest.mock import patch

import boto3


class Boto3Patcher:
    def __init__(self, **kwargs) -> None:
        self.services: dict[str, Callable] = kwargs or {}

    def dispatch(self, service: str, **kwargs):
        if service in self.services:
            return self.services[service](**kwargs)

        raise ValueError(f"Unpatched service: '{service}'")

    @contextmanager
    def handler_for(self, service: str, handler):
        with patch.dict(self.services, {service: handler}):
            yield


mocked_client = Boto3Patcher()
mocked_region = Boto3Patcher()

boto3_module_patching = patch.multiple(boto3, client=mocked_client.dispatch)
boto3_session_patching = patch.multiple(
    boto3.Session,
    client=mocked_client.dispatch,
    get_available_regions=mocked_region.dispatch,
)
