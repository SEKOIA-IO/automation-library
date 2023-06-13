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
        "LogFileLength": expected_response.get("LogFileLength"),
    }


@pytest.mark.asyncio
async def test_event_log_file_response(session_faker):
    """
    Test salesforce event log file response.

    Args:
        session_faker:
    """
    expected_response = {
        "totalSize": 4,
        "done": True,
        "records": [
            {
                "Id": "0ATD000000001bROAQ",
                "EventType": "API",
                "LogFile": "/services/data/v57.0/sobjects/EventLogFile/0ATD000000001bROAQ/LogFile",
                "LogDate": "2014-03-14T00:00:00.000+0000",
                "LogFileLength": 2692.0,
            },
            {
                "Id": "0ATD000000001SdOAI",
                "EventType": "API",
                "LogFile": "/services/data/v57.0/sobjects/EventLogFile/0ATD000000001SdOAI/LogFile",
                "LogDate": "2014-03-13T00:00:00.000+0000",
                "LogFileLength": 1345.0,
            },
            {
                "Id": "0ATD000000003p1OAA",
                "EventType": "API",
                "LogFile": "/services/data/v57.0/sobjects/EventLogFile/0ATD000000003p1OAA/LogFile",
                "LogDate": "2014-06-21T00:00:00.000+0000",
                "LogFileLength": 605.0,
            },
            {
                "Id": "0ATD0000000055eOAA",
                "EventType": "API",
                "LogFile": "/services/data/v57.0/sobjects/EventLogFile/0ATD0000000055eOAA/LogFile",
                "LogDate": "2014-07-03T00:00:00.000+0000",
                "LogFileLength": 605.0,
            },
        ],
    }

    response = SalesforceEventLogFilesResponse(**expected_response)

    assert isinstance(response, SalesforceEventLogFilesResponse)
    assert response.dict() == expected_response
