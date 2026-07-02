import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from office365.management_api.checkpoint import Checkpoint


@pytest.fixture
def intake_key():
    return str(uuid.uuid4())


@pytest.fixture
def checkpoint(symphony_storage, intake_key):
    return Checkpoint(symphony_storage, intake_key)


def test_non_existing_checkpoint(checkpoint):
    now = datetime.now(UTC)

    # Not set
    with (
        patch.object(Path, "read_text", side_effect=OSError),
        patch("office365.management_api.checkpoint.datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        # Timedelta is slightly less than 7 days since a few microseconds elapsed between `now`
        # and the moment `last_pull_date` is generated
        assert now == checkpoint.offset


def test_checkpoint_lesser_than_30_days(symphony_storage, checkpoint, intake_key):
    now = datetime.now(UTC)
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    context.write_text(now.isoformat())

    # Less than 7 days ago
    assert checkpoint.offset == now


def test_checkpoint_greater_than_7_days(symphony_storage, checkpoint, intake_key):
    now = datetime.now(UTC)
    current_cursor = now - timedelta(days=365)
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    context.write_text(current_cursor.isoformat())

    with patch("office365.management_api.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        # Timedelta is slightly less than 7 days since a few microseconds elapsed between `now`
        # and the moment `last_pull_date` is generated
        assert (now - checkpoint.offset).days == 7


def test_checkpoint_greater_than_7_days_bis(symphony_storage, checkpoint, intake_key):
    now = datetime(2024, 12, 18, 17, 26, 10, tzinfo=UTC)
    last_date_seen = datetime(2024, 12, 10, 15, 59, 1, tzinfo=UTC)
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    context.write_text(last_date_seen.isoformat())

    with patch("office365.management_api.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        # Timedelta is slightly less than 7 days since a few microseconds elapsed between `now`
        # and the moment `last_pull_date` is generated
        assert (now - checkpoint.offset).days == 7


def test_checkpoint_save_last_date(symphony_storage, checkpoint, intake_key):
    # arrange
    now = datetime.now(UTC)
    previous_observed_date = now - timedelta(days=5)
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    context.write_text(previous_observed_date.isoformat())

    # assert that the checkpoint is at the last observed date
    assert checkpoint.offset == previous_observed_date

    # save a more recent date in the checkpoint
    new_observed_date = now - timedelta(days=1)
    checkpoint.offset = new_observed_date

    # assert that the checkpoint was updated to the new observed date
    assert checkpoint.offset == new_observed_date


def test_read_retries_on_transient_error_then_succeeds(symphony_storage, checkpoint):
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    saved_data = datetime.now(UTC).isoformat()
    context.write_text(saved_data)

    calls = {"n": 0}

    real_open = Path.open

    def flaky_open(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("Can't access the file")

        return real_open(self, *args, **kwargs)

    with patch.object(Path, "open", flaky_open), patch("time.sleep") as mock_sleep:
        result = checkpoint.read(context)

    assert result == saved_data
    assert calls["n"] == 3  # two failures + one success


def test_read_exhausts_retries(symphony_storage, checkpoint):
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    saved_data = datetime.now(UTC).isoformat()
    context.write_text(saved_data)

    with (
        patch.object(Path, "open", side_effect=OSError("permanent failure")),
        patch("time.sleep") as mock_sleep,
        pytest.raises(OSError),
    ):
        checkpoint.read(context)


def test_write_retries_on_transient_error_then_succeeds(symphony_storage, checkpoint):
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    saved_data = datetime.now(UTC).isoformat()

    calls = {"n": 0}

    real_open = Path.open

    def flaky_open(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("Can't access the file")

        return real_open(self, *args, **kwargs)

    with patch.object(Path, "open", flaky_open), patch("time.sleep") as mock_sleep:
        checkpoint.write(context, saved_data)

    assert calls["n"] == 3  # two failures + one success


def test_write_exhausts_retries(symphony_storage, checkpoint):
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    saved_data = datetime.now(UTC).isoformat()

    with (
        patch.object(Path, "open", side_effect=OSError("permanent failure")),
        patch("time.sleep") as mock_sleep,
        pytest.raises(OSError),
    ):
        checkpoint.write(context, saved_data)
