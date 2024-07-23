"""Tests related to http client."""

import csv
import datetime
from unittest.mock import MagicMock

import aiocsv
import aiofiles
import pytest
from aiohttp import ClientResponse
from aioresponses import aioresponses

from client.http_client import LogType, SalesforceHttpClient
from client.schemas.log_file import EventLogFile, SalesforceEventLogFilesResponse
from utils.file_utils import delete_file


@pytest.mark.asyncio
async def test_salesforce_http_client_query_to_http_param():
    """Test SalesforceHttpClient._query_to_http_param."""
    http_param = SalesforceHttpClient._query_to_http_param("SELECT Id, Name FROM Account")

    expected_param = "SELECT+Id+,+Name+FROM+Account"

    assert http_param == expected_param


@pytest.mark.asyncio
async def test_salesforce_http_client_query_to_http_param_1():
    """Test SalesforceHttpClient._query_to_http_param."""
    http_param = SalesforceHttpClient._query_to_http_param(
        'SELECT Id, Name FROM Account WHERE Id = "123" AMD DateCreated >= "2021-01-01"'
    )

    expected_param = 'SELECT+Id+,+Name+FROM+Account+WHERE+Id+=+"123"+AMD+DateCreated+>=+"2021-01-01"'

    assert http_param == expected_param


@pytest.mark.asyncio
async def test_salesforce_http_client_log_files_query():
    """Test SalesforceHttpClient._log_files_query."""
    query = SalesforceHttpClient._log_files_query(None)

    expected_query = """
        SELECT Id, EventType, LogFile, LogDate, CreatedDate, LogFileLength
                FROM EventLogFile WHERE Interval = \'Hourly\'
    """.strip()

    assert query.strip() == expected_query


@pytest.mark.asyncio
async def test_salesforce_http_client_log_files_query_1():
    """Test SalesforceHttpClient._log_files_query."""
    query = SalesforceHttpClient._log_files_query(
        start_from=datetime.datetime.strptime("2023-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"),
    )

    expected_query = """
        SELECT Id, EventType, LogFile, LogDate, CreatedDate, LogFileLength
                FROM EventLogFile WHERE Interval = \'Hourly\' AND CreatedDate > 2023-01-01T00:00:00Z
    """.strip()

    assert query.strip() == expected_query


@pytest.mark.asyncio
async def test_salesforce_http_client_log_files_query_2():
    """Test SalesforceHttpClient._log_files_query."""
    query = SalesforceHttpClient._log_files_query(
        start_from=datetime.datetime.strptime("2023-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"),
        log_type=LogType.DAILY,
    )

    expected_query = """
        SELECT Id, EventType, LogFile, LogDate, CreatedDate, LogFileLength
                FROM EventLogFile WHERE Interval = \'Daily\' AND CreatedDate > 2023-01-01T00:00:00Z
    """.strip()

    assert query.strip() == expected_query


@pytest.mark.asyncio
async def test_salesforce_http_client_log_files_query_2():
    """Test SalesforceHttpClient._log_files_query."""
    query = SalesforceHttpClient._log_files_query(
        start_from=datetime.datetime.strptime("2023-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"),
        log_type=LogType.HOURLY,
    )

    expected_query = """
        SELECT Id, EventType, LogFile, LogDate, CreatedDate, LogFileLength
                FROM EventLogFile WHERE Interval = \'Hourly\' AND CreatedDate > 2023-01-01T00:00:00Z
    """.strip()

    assert query.strip() == expected_query


@pytest.mark.asyncio
async def test_salesforce_http_client_request_url_with_query(session_faker):
    """
    Test SalesforceHttpClient._request_url_with_query.

    Args:
        session_faker: Faker
    """
    base_url = session_faker.uri()
    query = "SELECT Id, Name FROM Account WHERE IsActive = True"

    client = SalesforceHttpClient(
        client_id=session_faker.pystr(),
        client_secret=session_faker.pystr(),
        base_url=base_url,
    )

    url = client._request_url_with_query(query)

    expected_url = "{0}/services/data/v58.0/query?q=SELECT+Id+,+Name+FROM+Account+WHERE+IsActive+=+True".format(
        base_url
    )

    assert str(url) == expected_url


@pytest.mark.asyncio
async def test_salesforce_http_client_request_headers(session_faker, http_token, token_refresher_session):
    """
    Test SalesforceHttpClient._request_headers.

    Args:
        session_faker: Faker
        http_token: HttpToken
        token_refresher_session: MagicMock
    """
    base_url = session_faker.uri()

    token_data = http_token.dict()
    token_data["id"] = token_data["tid"]

    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.return_value = token_data

    client = SalesforceHttpClient(
        client_id=session_faker.pystr(), client_secret=session_faker.pystr(), base_url=base_url
    )

    result_headers = await client._request_headers()

    assert result_headers == {
        "Authorization": "Bearer {0}".format(http_token.access_token),
        "Content-Type": "application/json",
        "Content-Encoding": "gzip",
    }


@pytest.mark.asyncio
async def test_salesforce_http_client_get_log_files(
    session_faker, http_token, token_refresher_session, http_client_session
):
    """
    Test SalesforceHttpClient.get_log_files.

    Args:
        session_faker: Faker
        token_refresher_session: MagicMock
        http_client_session: MagicMock
    """
    client = SalesforceHttpClient(
        client_id=session_faker.pystr(), client_secret=session_faker.pystr(), base_url=session_faker.uri()
    )

    token_data = http_token.dict()
    token_data["id"] = token_data["tid"]

    event_log_file = EventLogFile(
        Id=session_faker.pystr(),
        EventType=session_faker.pystr(),
        LogFile=session_faker.pystr(),
        LogDate=session_faker.date_time().isoformat(),
        CreatedDate=session_faker.date_time().isoformat(),
        LogFileLength=session_faker.pyfloat(),
    )

    log_files_response_success = SalesforceEventLogFilesResponse(totalSize=1, done=True, records=[event_log_file])

    log_files_response_failed = SalesforceEventLogFilesResponse(totalSize=0, done=False, records=[])

    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.return_value = token_data

    http_client_session.get = MagicMock()
    http_client_session.get.return_value.__aenter__.return_value.status = 200
    http_client_session.get.return_value.__aenter__.return_value.json.return_value = log_files_response_success.dict()

    client_result = await client.get_log_files()
    assert client_result == log_files_response_success

    http_client_session.get.return_value.__aenter__.return_value.json.return_value = log_files_response_failed.dict()

    with pytest.raises(ValueError):
        await client.get_log_files()


@pytest.mark.asyncio
async def test_salesforce_http_client_handle_error_response():
    response = MagicMock(spec=ClientResponse)
    response.status = 200

    await SalesforceHttpClient._handle_error_response(response)

    assert True


@pytest.mark.asyncio
async def test_salesforce_http_client_error_response_with_non_200_status(session_faker):
    """
    Test SalesforceHttpClient._handle_error_response with a non-200 status code.

    Args:
        session_faker: Faker
    """
    response = MagicMock(spec=ClientResponse)

    error_code = session_faker.word()
    error_message = session_faker.sentence()

    response.status = 404
    response.json.return_value = [{"errorCode": error_code, "message": error_message}]

    try:
        # Call the function
        await SalesforceHttpClient._handle_error_response(response)
        # If the function didn't raise an exception, fail the test
        pytest.fail("Exception not raised")
    except Exception as e:
        assert str(e) == "Error {0}: {1}".format(error_code, error_message)


@pytest.mark.asyncio
async def test_salesforce_http_client_get_log_file_content(session_faker, http_token, csv_content):
    """
    Test SalesforceHttpClient.get_log_file_content.

    Args:
        session_faker: Faker
        http_token: SalesforceToken
        csv_content: str
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()

        log_file = EventLogFile(
            Id=session_faker.pystr(),
            EventType=session_faker.pystr(),
            LogFile=session_faker.pystr(),
            LogDate=session_faker.date_time().isoformat(),
            CreatedDate=session_faker.date_time().isoformat(),
            LogFileLength=session_faker.pyfloat(),
        )

        client = SalesforceHttpClient(
            client_id=session_faker.pystr(), client_secret=session_faker.pystr(), base_url=base_url
        )

        token_data = http_token.dict()
        token_data["id"] = token_data["tid"]

        mocked_responses.post(
            "{0}/services/oauth2/token?grant_type=client_credentials".format(base_url), status=200, payload=token_data
        )

        mocked_responses.get(
            url="{0}{1}".format(base_url, log_file.LogFile),
            status=200,
            body=csv_content.encode("utf-8"),
            headers={"Content-Length": "1"},
        )

        result_content, result_file = await client.get_log_file_content(log_file, persist_to_file=False)

        assert result_content == list(csv.DictReader(csv_content.splitlines(), delimiter=","))
        assert result_file is None


@pytest.mark.asyncio
async def test_salesforce_http_client_get_log_file_content_2(session_faker, http_token, csv_content):
    """
    Test SalesforceHttpClient.get_log_file_content.

    Args:
        session_faker: Faker
        http_token: SalesforceToken
        csv_content: str
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()

        log_file = EventLogFile(
            Id=session_faker.pystr(),
            EventType=session_faker.pystr(),
            LogFile=session_faker.pystr(),
            LogDate=session_faker.date_time().isoformat(),
            CreatedDate=session_faker.date_time().isoformat(),
            LogFileLength=session_faker.pyfloat(),
        )

        client = SalesforceHttpClient(
            client_id=session_faker.pystr(), client_secret=session_faker.pystr(), base_url=base_url
        )

        token_data = http_token.dict()
        token_data["id"] = token_data["tid"]

        mocked_responses.post(
            "{0}/services/oauth2/token?grant_type=client_credentials".format(base_url), status=200, payload=token_data
        )

        mocked_responses.get(
            url="{0}{1}".format(base_url, log_file.LogFile),
            status=200,
            body=csv_content.encode("utf-8"),
            headers={"Content-Length": "1"},
        )

        result_content, result_file = await client.get_log_file_content(log_file, persist_to_file=True)

        assert result_content is None
        assert result_file is not None

        file_content = []
        async with aiofiles.open(result_file, encoding="utf-8") as file:
            async for row in aiocsv.AsyncDictReader(file, delimiter=","):
                file_content.append(row)

        await delete_file(result_file)

        assert file_content == list(csv.DictReader(csv_content.splitlines(), delimiter=","))
