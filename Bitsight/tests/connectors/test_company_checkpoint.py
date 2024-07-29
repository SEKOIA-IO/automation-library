from datetime import datetime, timedelta, timezone

from connectors.pull_findings_trigger import CompanyCheckpoint


def test_with_updated_last_seen_none():
    """
    Test that the last_seen date is updated if it is None.
    """
    now = datetime.now(timezone.utc)
    expected_last_seen = (
        (now - timedelta(days=7)).replace(microsecond=0, second=0, minute=0, hour=0).strftime("%Y-%m-%d")
    )
    checkpoint = CompanyCheckpoint(company_uuid="test-uuid", last_seen=None, offset=None)
    updated_checkpoint = checkpoint.with_updated_last_seen()
    assert updated_checkpoint.last_seen == expected_last_seen
    assert updated_checkpoint.offset is None


def test_with_updated_last_seen_older_than_7_days():
    """
    Test that the last_seen date is updated if it is older than 7 days.
    """
    old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc)
    expected_last_seen = (
        (now - timedelta(days=7)).replace(microsecond=0, second=0, minute=0, hour=0).strftime("%Y-%m-%d")
    )
    checkpoint = CompanyCheckpoint(company_uuid="test-uuid", last_seen=old_date, offset=123)
    updated_checkpoint = checkpoint.with_updated_last_seen()
    assert updated_checkpoint.last_seen == expected_last_seen
    assert updated_checkpoint.offset is None


def test_with_updated_last_seen_within_7_days_1():
    """
    Test that the last_seen date is not updated if it is within 7 days.
    """
    recent_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
    checkpoint = CompanyCheckpoint(company_uuid="test-uuid", last_seen=recent_date, offset=None)
    updated_checkpoint = checkpoint.with_updated_last_seen()
    assert updated_checkpoint.last_seen == recent_date
    assert updated_checkpoint.offset is None


def test_with_updated_last_seen_within_7_days_2():
    """
    Test that the last_seen date is not updated if it is within 7 days.
    """
    recent_date = (
        datetime.now(timezone.utc).replace(microsecond=0, second=0, minute=0, hour=0) - timedelta(days=7)
    ).strftime("%Y-%m-%d")

    checkpoint = CompanyCheckpoint(company_uuid="test-uuid", last_seen=recent_date, offset=123)
    assert checkpoint.with_updated_last_seen() == checkpoint
