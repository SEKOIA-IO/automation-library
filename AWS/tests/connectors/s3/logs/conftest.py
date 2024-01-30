"""Some useful mocks for AWS services."""

import pytest

from .mock import boto3_module_patching, boto3_session_patching


@pytest.fixture
def aws_mock() -> None:
    with boto3_module_patching, boto3_session_patching:
        yield
