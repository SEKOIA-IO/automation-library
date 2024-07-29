"""Tests related to connector."""

from datetime import datetime, timedelta, timezone
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, MagicMock

import pytest
from aioresponses import aioresponses
from sekoia_automation import constants

from client.http_client import LogType
from client.schemas.log_file import EventLogFile, SalesforceEventLogFilesResponse
from salesforce import SalesforceModule
from salesforce.connector import SalesforceConnector, SalesforceConnectorConfig
from salesforce.models import SalesforceModuleConfig


@pytest.fixture
def symphony_storage() -> str:
    """
    Fixture for symphony temporary storage.

    Yields:
        str:
    """
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage


@pytest.fixture
def client_id(session_faker) -> str:
    """
    Generate random client_id.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word()


@pytest.fixture
def client_secret(session_faker) -> str:
    """
    Generate random client_secret.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word() + session_faker.word()


@pytest.fixture
def salesforce_url(session_faker) -> str:
    """
    Generate random uri.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.uri()


@pytest.fixture
def pushed_events_ids(session_faker) -> list[str]:
    """
    Generate random list of events ids.

    Args:
        session_faker: Faker

    Returns:
        list[str]:
    """
    return [session_faker.word() for _ in range(session_faker.random.randint(1, 10))]


@pytest.fixture
def connector(symphony_storage, client_id, client_secret, salesforce_url, pushed_events_ids, session_faker):
    module = SalesforceModule()
    config = SalesforceConnectorConfig(
        intake_key=session_faker.word(),
    )
    trigger = SalesforceConnector(
        module=module,
        data_path=symphony_storage,
    )

    # Mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    # Mock the push_events_to_intakes function
    trigger.push_data_to_intakes = AsyncMock(return_value=pushed_events_ids)

    trigger.module.configuration = SalesforceModuleConfig(
        client_id=client_id, client_secret=client_secret, base_url=salesforce_url
    )

    trigger.configuration = config

    return trigger


@pytest.mark.asyncio
async def test_salesforce_connector_last_event_date(connector):
    """
    Test `last_event_date`.

    Args:
        connector: SalesforceConnector
    """
    with connector.context as cache:
        cache["last_event_date"] = None

    current_date = datetime.now(timezone.utc).replace(microsecond=0)
    one_hour_ago = current_date - timedelta(hours=1)

    assert connector.last_event_date == one_hour_ago

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    assert connector.last_event_date == current_date

    with connector.context as cache:
        cache["last_event_date"] = (one_hour_ago - timedelta(minutes=20)).isoformat()

    assert connector.last_event_date == one_hour_ago


@pytest.mark.asyncio
async def test_salesforce_connector_salesforce_client(connector):
    """
    Test salesforce client initialization.

    Args:
        connector: SalesforceConnector
    """
    assert connector._salesforce_client is None

    client1 = connector.salesforce_client
    client2 = connector.salesforce_client

    assert client1 is client2 is connector._salesforce_client


@pytest.mark.asyncio
async def test_module_configuration(session_faker):
    """
    Test module configuration.

    Returns:
        None:
    """
    config_1 = SalesforceModuleConfig(
        client_secret=session_faker.pystr(),
        client_id=session_faker.pystr(),
        base_url=session_faker.uri(),
    )

    assert config_1.rate_limiter.max_rate == 25
    assert config_1.rate_limiter.time_period == 20

    config_2 = SalesforceModuleConfig(
        client_secret=session_faker.pystr(),
        client_id=session_faker.pystr(),
        base_url=session_faker.uri(),
        org_type="sandbox",
    )

    assert config_2.rate_limiter.max_rate == 25
    assert config_2.rate_limiter.time_period == 20

    config_3 = SalesforceModuleConfig(
        client_secret=session_faker.pystr(),
        client_id=session_faker.pystr(),
        base_url=session_faker.uri(),
        org_type="developer",
    )

    assert config_3.rate_limiter.max_rate == 5
    assert config_3.rate_limiter.time_period == 20

    config_4 = SalesforceModuleConfig(
        client_secret=session_faker.pystr(),
        client_id=session_faker.pystr(),
        base_url=session_faker.uri(),
        org_type="trial",
    )

    assert config_4.rate_limiter.max_rate == 5
    assert config_4.rate_limiter.time_period == 20

    config_5 = SalesforceModuleConfig(
        client_secret=session_faker.pystr(),
        client_id=session_faker.pystr(),
        base_url=session_faker.uri(),
        org_type=session_faker.word(),
    )

    assert config_5.rate_limiter.max_rate == 5
    assert config_5.rate_limiter.time_period == 20


@pytest.mark.asyncio
async def test_salesforce_connector_get_salesforce_events(
    connector: SalesforceConnector, session_faker, http_token, csv_content, salesforce_url, pushed_events_ids
):
    """
    Test salesforce connector get salesforce events.

    Args:
        connector: SalesforceConnector
        session_faker: Faker
        http_token: HttpToken
        csv_content: str
        salesforce_url: str
    """
    log_file_date = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)

    event_log_file = EventLogFile(
        Id=session_faker.pystr(),
        EventType=session_faker.pystr(),
        LogFile=session_faker.pystr(),
        LogDate=log_file_date.isoformat(),
        CreatedDate=log_file_date.isoformat(),
        LogFileLength=len(csv_content.encode("utf-8")),
    )

    log_files_response_success = SalesforceEventLogFilesResponse(totalSize=1, done=True, records=[event_log_file])

    token_data = http_token.dict()
    token_data["id"] = token_data["tid"]

    with aioresponses() as mocked_responses:
        mocked_responses.post(
            "{0}/services/oauth2/token?grant_type=client_credentials".format(salesforce_url),
            status=200,
            payload=token_data,
        )

        query = connector.salesforce_client._log_files_query(connector.last_event_date)
        get_log_files_url = connector.salesforce_client._request_url_with_query(query)

        log_file_response_dict = log_files_response_success.dict()
        log_file_response_dict["records"] = [token_data]

        mocked_responses.get(
            get_log_files_url,
            payload=log_files_response_success.dict(),
        )

        mocked_responses.get(
            url="{0}{1}".format(salesforce_url, event_log_file.LogFile),
            status=200,
            body=csv_content.encode("utf-8"),
            headers={"Content-Length": "{0}".format(len(csv_content.encode("utf-8")))},
        )

        result = await connector.get_salesforce_events()

        assert result == pushed_events_ids


@pytest.mark.asyncio
async def test_salesforce_connector_get_salesforce_events_1(
    connector: SalesforceConnector, session_faker, http_token, csv_content, salesforce_url, pushed_events_ids
):
    """
    Test salesforce connector get salesforce events.

    Args:
        connector: SalesforceConnector
        session_faker: Faker
        http_token: HttpToken
        csv_content: str
        salesforce_url: str
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)
    log_file_date = current_date - timedelta(days=1)

    # Try to put last event date higher to be 1 day ahead of the log file date
    with connector.context as cache:
        cache["last_event_date"] = (current_date + timedelta(days=1)).isoformat()

    event_log_file = EventLogFile(
        Id=session_faker.pystr(),
        EventType=session_faker.pystr(),
        LogFile=session_faker.pystr(),
        LogDate=log_file_date.isoformat(),
        CreatedDate=log_file_date.isoformat(),
        LogFileLength=1024 * 1024 * 1024,
    )

    log_files_response_success = SalesforceEventLogFilesResponse(totalSize=1, done=True, records=[event_log_file])

    token_data = http_token.dict()
    token_data["id"] = token_data["tid"]

    with aioresponses() as mocked_responses:
        mocked_responses.post(
            "{0}/services/oauth2/token?grant_type=client_credentials".format(salesforce_url),
            status=200,
            payload=token_data,
        )

        query = connector.salesforce_client._log_files_query(connector.last_event_date)
        get_log_files_url = connector.salesforce_client._request_url_with_query(query)

        log_file_response_dict = log_files_response_success.dict()
        log_file_response_dict["records"] = [token_data]

        mocked_responses.get(
            get_log_files_url,
            payload=log_files_response_success.dict(),
        )

        # We try to return too large file to process it memory at this place, putting Content-Length to 1GB
        mocked_responses.get(
            url="{0}{1}".format(salesforce_url, event_log_file.LogFile),
            status=200,
            body=csv_content.encode("utf-8"),
            headers={"Content-Length": "{0}".format(1024 * 1024 * 1024)},
        )

        result = await connector.get_salesforce_events()

        expected_result = []
        [expected_result.extend(pushed_events_ids) for _ in range(1, len(csv_content.splitlines()))]

        assert result == expected_result


@pytest.mark.asyncio
async def test_salesforce_connector_get_salesforce_events_2(
    connector: SalesforceConnector, session_faker, http_token, csv_content, salesforce_url, pushed_events_ids
):
    """
    Test salesforce connector get salesforce events.

    Args:
        connector: SalesforceConnector
        session_faker: Faker
        http_token: HttpToken
        csv_content: str
        salesforce_url: str
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)
    log_file_date = current_date - timedelta(days=1)
    connector.configuration.fetch_daily_logs = True

    # Try to put last event date higher to be 1 day ahead of the log file date
    with connector.context as cache:
        cache["last_event_date"] = (current_date + timedelta(days=1)).isoformat()

    event_log_file = EventLogFile(
        Id=session_faker.pystr(),
        EventType=session_faker.pystr(),
        LogFile=session_faker.pystr(),
        LogDate=log_file_date.isoformat(),
        CreatedDate=log_file_date.isoformat(),
        LogFileLength=1024 * 1024 * 1024,
    )

    log_files_response_success = SalesforceEventLogFilesResponse(totalSize=1, done=True, records=[event_log_file])

    token_data = http_token.dict()
    token_data["id"] = token_data["tid"]

    with aioresponses() as mocked_responses:
        mocked_responses.post(
            "{0}/services/oauth2/token?grant_type=client_credentials".format(salesforce_url),
            status=200,
            payload=token_data,
        )

        query = connector.salesforce_client._log_files_query(connector.last_event_date, LogType.DAILY)
        get_log_files_url = connector.salesforce_client._request_url_with_query(query)

        log_file_response_dict = log_files_response_success.dict()
        log_file_response_dict["records"] = [token_data]

        mocked_responses.get(
            get_log_files_url,
            payload=log_files_response_success.dict(),
        )

        # We try to return too large file to process it memory at this place, putting Content-Length to 1GB
        mocked_responses.get(
            url="{0}{1}".format(salesforce_url, event_log_file.LogFile),
            status=200,
            body=csv_content.encode("utf-8"),
            headers={"Content-Length": "{0}".format(1024 * 1024 * 1024)},
        )

        result = await connector.get_salesforce_events()

        expected_result = []
        [expected_result.extend(pushed_events_ids) for _ in range(1, len(csv_content.splitlines()))]

        assert result == expected_result
