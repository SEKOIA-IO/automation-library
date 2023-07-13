"""Tests to handle Salesforce response data."""

import pytest

from client.schemas.log_file import EventLogFile, SalesforceEventLogFilesResponse


@pytest.mark.asyncio
async def test_event_log_file(session_faker):
    """
    Test salesforce event log file entity.

    Args:
        session_faker:
    """
    expected_response = {
        "attributes": {"type": "EventLogFile", "url": session_faker.uri()},
        "Id": session_faker.word(),
        "EventType": "Api",
        "CreatedDate": session_faker.date_time().strftime("%Y-%m-%d"),
        "LogDate": session_faker.date_time().strftime("%Y-%m-%d"),
        "LogFile": session_faker.uri(),
        "LogFileLength": session_faker.random_int(),
        "Sequence": session_faker.random_int(),
        "Size": session_faker.random_int(),
        "SystemModstamp": session_faker.date_time().strftime("%Y-%m-%d"),
    }

    response = EventLogFile(**expected_response)

    assert isinstance(response, EventLogFile)
    assert response.dict() == {
        "Id": expected_response.get("Id"),
        "EventType": expected_response.get("EventType"),
        "LogFile": expected_response.get("LogFile"),
        "LogDate": expected_response.get("LogDate"),
        "CreatedDate": expected_response.get("CreatedDate"),
        "LogFileLength": expected_response.get("LogFileLength"),
    }


@pytest.mark.asyncio
async def test_event_log_file_response(session_faker):
    """
    Test salesforce event log file response.

    Args:
        session_faker:
    """
    records = [
        {
            "Id": session_faker.word(),
            "EventType": session_faker.word(),
            "LogFile": session_faker.uri(),
            "LogDate": session_faker.date_time().strftime("%Y-%m-%d"),
            "CreatedDate": session_faker.date_time().strftime("%Y-%m-%d"),
            "LogFileLength": session_faker.pyfloat(),
        }
        for _ in range(session_faker.random_int(1, 10))
    ]

    expected_response = {
        "totalSize": len(records),
        "done": True,
        "records": records,
    }

    response = SalesforceEventLogFilesResponse(**expected_response)

    assert isinstance(response, SalesforceEventLogFilesResponse)
    assert response.dict() == expected_response
