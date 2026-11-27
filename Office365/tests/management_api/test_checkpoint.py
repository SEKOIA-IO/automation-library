import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from office365.management_api.checkpoint import Checkpoint

NOW = datetime(2024, 12, 18, 17, 26, 10, tzinfo=UTC)


@pytest.fixture
def intake_key():
    return str(uuid.uuid4())


@pytest.fixture
def checkpoint(symphony_storage, intake_key):
    return Checkpoint(symphony_storage, intake_key)


@pytest.fixture
def context(symphony_storage, intake_key) -> Path:
    return symphony_storage / f"o365_{intake_key}_last_pull"


@pytest.fixture
def mock_now():
    with patch("office365.management_api.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = NOW
        yield mock_datetime


def test_non_existing_checkpoint(checkpoint, mock_now):
    with patch.object(Path, "read_text", side_effect=OSError):
        assert checkpoint.offset == NOW


@pytest.mark.parametrize(
    "saved_offset,expected_offset",
    [
        pytest.param(NOW, NOW, id="now"),
        pytest.param(NOW - timedelta(days=5), NOW - timedelta(days=5), id="less_than_7_days"),
        pytest.param(datetime(2024, 12, 10, 15, 59, 1, tzinfo=UTC), NOW - timedelta(days=7), id="8_days"),
        pytest.param(NOW - timedelta(days=365), NOW - timedelta(days=7), id="one_year"),
    ],
)
def test_checkpoint_offset(checkpoint, context, mock_now, saved_offset, expected_offset):
    context.write_text(saved_offset.isoformat())

    assert checkpoint.offset == expected_offset


SAVED_OFFSET = NOW - timedelta(days=2)


@pytest.mark.parametrize(
    "new_offset,expected_offset",
    [
        pytest.param(None, SAVED_OFFSET, id="none_is_ignored"),
        pytest.param(SAVED_OFFSET - timedelta(days=1), SAVED_OFFSET, id="older_date_is_ignored"),
        pytest.param(
            SAVED_OFFSET + timedelta(days=1), SAVED_OFFSET + timedelta(days=1), id="more_recent_date_is_saved"
        ),
    ],
)
def test_checkpoint_offset_setter(checkpoint, context, mock_now, new_offset, expected_offset):
    context.write_text(SAVED_OFFSET.isoformat())

    checkpoint.offset = new_offset

    assert checkpoint.offset == expected_offset
    assert context.read_text() == expected_offset.isoformat()


def read_operation(checkpoint, context, data):
    return checkpoint.read(context)


def write_operation(checkpoint, context, data):
    return checkpoint.write(context, data)


FILE_OPERATIONS = [
    pytest.param(read_operation, id="read"),
    pytest.param(write_operation, id="write"),
]


@pytest.mark.parametrize(
    "operation,returns_data",
    [
        pytest.param(read_operation, True, id="read_returns_the_data"),
        pytest.param(write_operation, False, id="write_returns_nothing"),
    ],
)
def test_file_operation_retries_on_transient_error_then_succeeds(checkpoint, context, operation, returns_data):
    calls = {"n": 0}
    real_open = Path.open

    def flaky_open(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("Can't access the file")

        return real_open(self, *args, **kwargs)

    data = NOW.isoformat()
    context.write_text(data)

    with patch.object(Path, "open", flaky_open):
        result = operation(checkpoint, context, data)

    assert calls["n"] == 3  # two failures + one success
    assert result == (data if returns_data else None)
    assert context.read_text() == data


@pytest.mark.parametrize("operation", FILE_OPERATIONS)
def test_file_operation_exhausts_retries(checkpoint, context, operation):
    context.write_text(NOW.isoformat())

    with (
        patch.object(Path, "open", side_effect=OSError("permanent failure")),
        pytest.raises(OSError),
    ):
        operation(checkpoint, context, NOW.isoformat())


def test_read_returns_none_when_file_does_not_exist(checkpoint, context):
    assert checkpoint.read(context) is None
