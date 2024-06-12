import uuid
from datetime import datetime, timedelta, timezone
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
    now = datetime.now(timezone.utc)

    # Not set
    with (
        patch.object(Path, "read_text", side_effect=FileNotFoundError),
        patch("office365.management_api.checkpoint.datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        # Timedelta is sligthly less than 7 days since a few microseconds elapsed between `now`
        # and the moment `last_pull_date` is generated
        assert now == checkpoint.offset


def test_checkpoint_lesser_than_30_days(symphony_storage, checkpoint, intake_key):
    now = datetime.now(timezone.utc)
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    context.write_text(now.isoformat())

    # Less than 7 days ago
    assert checkpoint.offset == now


def test_checkpoint_greater_than_30_days(symphony_storage, checkpoint, intake_key):
    now = datetime.now(timezone.utc)
    current_cursor = now - timedelta(days=365)
    context = symphony_storage / f"o365_{intake_key}_last_pull"
    context.write_text(current_cursor.isoformat())

    with patch("office365.management_api.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        # Timedelta is sligthly less than 30 days since a few microseconds elapsed between `now`
        # and the moment `last_pull_date` is generated
        assert (now - checkpoint.offset).days == 30
