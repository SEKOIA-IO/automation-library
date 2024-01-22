"""Tests related to client."""
from datetime import datetime, timedelta

import aiofiles
import pytest
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from aioresponses import aioresponses
from faker import Faker
from sekoia_automation.aio.helpers.files.utils import delete_file

from client.broadcom_cloud_swg_client import BroadcomCloudSwgClient


@pytest.fixture()
def client(session_faker: Faker) -> BroadcomCloudSwgClient:
    """
    Creates BroadcomCloudSwgClient.

    Returns:
        BroadcomCloudSwgClient:
    """
    return BroadcomCloudSwgClient(
        username=session_faker.word(),
        password=session_faker.word(),
        base_url=session_faker.uri(),
    )


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_client_session(client: BroadcomCloudSwgClient):
    """
    Test session initialization.

    Args:
        client: BroadcomCloudSwgClient
    """
    BroadcomCloudSwgClient._session = None

    assert BroadcomCloudSwgClient._session is None
    async with client.session() as session:
        assert isinstance(session, ClientSession)

    assert BroadcomCloudSwgClient._session is not None


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_client_get_real_time_log_data_url(
    client: BroadcomCloudSwgClient,
    session_faker: Faker,
):
    """
    Test get_real_time_log_data_url method.

    Args:
        client: BroadcomCloudSwgClient
        session_faker: Faker
    """
    end_date_now = datetime.utcnow()
    first_start_date = end_date_now - timedelta(days=session_faker.random.randint(1, 30))

    first_result = client.get_real_time_log_data_url(
        start_date=first_start_date,
        end_date=end_date_now,
    )

    first_expected_result = "{0}/reportpod/logs/sync?endDate={1}&startDate={2}&maxMb=100&token=none".format(
        client.base_url,
        int(end_date_now.timestamp()) * 1000,
        int(first_start_date.timestamp()) * 1000,
    )

    assert str(first_result) == first_expected_result

    second_start_date = end_date_now - timedelta(days=session_faker.random.randint(1, 30))
    token = session_faker.word()
    max_mb = session_faker.random.randint(1, 100)

    second_result = client.get_real_time_log_data_url(
        start_date=second_start_date, end_date=end_date_now, token=token, max_mb=max_mb
    )

    second_expected_result = "{0}/reportpod/logs/sync?endDate={1}&startDate={2}&maxMb={3}&token={4}".format(
        client.base_url, int(end_date_now.timestamp()) * 1000, int(second_start_date.timestamp()) * 1000, max_mb, token
    )

    assert str(second_result) == second_expected_result


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_client_get_report_sync_exception(
    client: BroadcomCloudSwgClient,
    session_faker: Faker,
    logs_content: str,
):
    """
    Test BroadcomCloudSwgClient get_report_sync.

    Args:
        client: BroadcomCloudSwgClient
        session_faker: Faker
    """
    with aioresponses() as mocked_responses:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=session_faker.random.randint(1, 29))

        requested_url = client.get_real_time_log_data_url(start_date=start_date, end_date=end_date)
        token = session_faker.word()

        mocked_responses.get(
            requested_url,
            status=401,
            body=logs_content.encode("utf-8"),
            headers={"X-sync-status": "done", "X-sync-token": token},
        )

        with pytest.raises(ValueError):
            await client.get_report_sync(
                start_date=start_date,
                end_date=end_date,
                token=None,
            )


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_client_get_report_sync_1(
    client: BroadcomCloudSwgClient,
    session_faker: Faker,
    logs_content: str,
):
    """
    Test BroadcomCloudSwgClient get_report_sync.

    Expect to have `X-sync-status` as `done`, valid token and status 200 with content.

    Args:
        client: BroadcomCloudSwgClient
        session_faker: Faker
    """
    with aioresponses() as mocked_responses:
        end_date = datetime.utcnow()
        # If start date is < 30 days ago it should limit to 30 days ago
        start_date = end_date - timedelta(days=session_faker.random.randint(1, 29))

        first_url = client.get_real_time_log_data_url(start_date=start_date, end_date=end_date)
        token = session_faker.word()

        mocked_responses.get(
            first_url,
            status=200,
            body=logs_content.encode("utf-8"),
            headers={"X-sync-status": "done", "X-sync-token": token},
        )

        # Do not pass token
        continue_work, result_token, result_file = await client.get_report_sync(
            start_date=start_date,
            end_date=end_date,
            token=None,
        )

        file_content = []

        async with aiofiles.open(result_file, encoding="utf-8") as file:
            async for line in file:
                file_content.append(line)

        await delete_file(result_file)

        assert "".join(file_content) == logs_content
        assert continue_work is False
        assert result_token == token


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_client_get_report_sync_2(
    client: BroadcomCloudSwgClient,
    session_faker: Faker,
    logs_content: str,
):
    """
    Test BroadcomCloudSwgClient get_report_sync.

    Expect to have `X-sync-status` as `more`, valid token and status 200 with content.

    Args:
        client: BroadcomCloudSwgClient
        session_faker: Faker
    """
    async_limiter = AsyncLimiter(10, 1)

    client.set_rate_limiter(async_limiter)

    with aioresponses() as mocked_responses:
        end_date = datetime.utcnow()

        expected_start_date = end_date - timedelta(days=30)
        input_token = session_faker.word()

        url = client.get_real_time_log_data_url(start_date=expected_start_date, end_date=end_date, token=input_token)

        response_token = session_faker.word()

        mocked_responses.get(
            url,
            status=200,
            body=logs_content.encode("utf-8"),
            headers={"X-sync-status": "more", "X-sync-token": response_token},
        )

        # Do not pass token
        continue_work, result_token, result_file = await client.get_report_sync(
            start_date=None,
            end_date=end_date,
            token=input_token,
        )

        file_content = []

        async with aiofiles.open(result_file, encoding="utf-8") as file:
            async for line in file:
                file_content.append(line)

        await delete_file(result_file)

        assert continue_work is True
        assert result_token == response_token
        assert "".join(file_content) == logs_content


@pytest.mark.asyncio
async def test_parse_input_string():
    """Test parse_input_string method."""

    input_string = "value1\tvalue2\tvalue3"
    expected_output = {"field1": "value1", "field2": "value2", "field3": "value3"}
    result = BroadcomCloudSwgClient.parse_input_string(input_string, fields=["field1", "field2", "field3"])
    assert result == expected_output

    input_string = "value1\tvalue2\tvalue3\tvalue4"
    default_fields = BroadcomCloudSwgClient.full_list_of_elff_fields()
    expected_output = {
        default_fields[0]: "value1",
        default_fields[1]: "value2",
        default_fields[2]: "value3",
        default_fields[3]: "value4",
    }
    result = BroadcomCloudSwgClient.parse_input_string(input_string)
    assert result == expected_output


@pytest.mark.asyncio
async def test_parse_string_as_headers():
    """Test parse_string_as_headers method."""

    input_string = "#Fields:\tfield1\tfield2\tfield3"
    result = BroadcomCloudSwgClient.parse_string_as_headers(input_string)
    assert result == []

    input_string = "#Fields:\t{0}".format("\t".join(BroadcomCloudSwgClient.full_list_of_elff_fields()))
    result = BroadcomCloudSwgClient.parse_string_as_headers(input_string)
    assert result == BroadcomCloudSwgClient.full_list_of_elff_fields()

    input_string = "value1\tvalue2\tvalue3"
    result = BroadcomCloudSwgClient.parse_string_as_headers(input_string)
    assert result is None

    input_string = "Fields: field1\tfield2\tfield3"
    result = BroadcomCloudSwgClient.parse_string_as_headers(input_string)
    assert result is None


@pytest.mark.asyncio
async def test_reduce_list_1():
    """Test to check if reduce_list() method provides correct results"""

    # As simple as possible. All values relates to one group
    sample_data = [
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 200,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 10,
            "time": "12:00:00",
        },
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 200,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 15,
            "time": "12:00:01",
        },
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 200,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 20,
            "time": "12:01:00",
        },
    ]

    result = BroadcomCloudSwgClient.reduce_list(sample_data)

    assert len(result) == 1
    assert result[0]["count"] == 3
    assert result[0]["time-taken"] == 20
    assert result[0]["start-time"] == "12:00:00"
    assert result[0]["end-time"] == "12:01:00"

    assert BroadcomCloudSwgClient.reduce_list([]) == []


@pytest.mark.asyncio
async def test_reduce_list_2():
    """Test to check if reduce_list() method provides correct results"""

    sample_data = [
        # this group should have 125 values but existed value should have min start, max end time and count
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 200,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 433,
            "time": "12:00:00",
            "start-time": "11:00:00",
            "end-time": "18:00:00",
            "count": 123,
        },
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 200,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 15,
            "time": "13:00:01",
        },
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 200,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 15,
            "time": "14:00:01",
        },
        # this group does not contain any additional values
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 202,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 8,
            "time": "12:01:00",
        },
        # this group should have 11 values and existed value have start and end time
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 203,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 74,
            "time": "12:00:00",
            "start-time": "11:22:33",
            "end-time": "12:00:00",
            "count": 10,
        },
        {
            "c-ip": "127.0.0.1",
            "cs-userdn": "user1",
            "s-action": "GET",
            "s-ip": "192.168.1.1",
            "sc-status": 203,
            "cs-method": "GET",
            "cs-host": "example.com",
            "cs-uri-path": "/path1",
            "time-taken": 79,
            "time": "19:19:19",
        },
    ]

    result = BroadcomCloudSwgClient.reduce_list(sample_data)

    assert len(result) == 3

    assert result[0]["count"] == 125
    assert result[0]["time-taken"] == 433
    assert result[0]["start-time"] == "11:00:00"
    assert result[0]["end-time"] == "18:00:00"

    assert result[1]["count"] == 1
    assert result[1]["time-taken"] == 8
    assert result[1]["start-time"] == "12:01:00"
    assert result[1]["end-time"] == "12:01:00"

    assert result[2]["count"] == 11
    assert result[2]["time-taken"] == 79
    assert result[2]["start-time"] == "11:22:33"
    assert result[2]["end-time"] == "19:19:19"
