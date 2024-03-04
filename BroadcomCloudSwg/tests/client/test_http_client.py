"""Tests related to client."""

from datetime import datetime, timedelta

import aiofiles
import pytest
import pytz
from aiohttp_retry import RetryClient
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
        assert isinstance(session, RetryClient)

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
    end_date_now = datetime.now(tz=pytz.utc)
    first_start_date = end_date_now - timedelta(seconds=session_faker.random.randint(1, 30))

    first_result, first_result_timestamp = client.get_real_time_log_data_url(
        start_date=first_start_date,
    )

    first_expected_result = "{0}/reportpod/logs/sync?endDate={1}&startDate={2}&token=none".format(
        client.base_url,
        0,
        int(first_start_date.replace(minute=0, second=0, microsecond=0).timestamp()) * 1000,
    )

    assert str(first_result) == first_expected_result

    second_start_date = end_date_now - timedelta(hours=1)
    token = session_faker.word()
    max_mb = session_faker.random.randint(1, 100)

    second_result, second_result_timestamp = client.get_real_time_log_data_url(
        start_date=second_start_date, token=token, max_mb=max_mb
    )

    second_expected_result = "{0}/reportpod/logs/sync?endDate={1}&startDate={2}&token={3}".format(
        client.base_url,
        int(end_date_now.replace(minute=0, second=0, microsecond=0).timestamp()) * 1000,
        int(second_start_date.replace(minute=0, second=0, microsecond=0).timestamp()) * 1000,
        token,
    )

    assert str(second_result) == second_expected_result

    third_start_date = end_date_now - timedelta(days=session_faker.random.randint(1, 30))
    with pytest.raises(ValueError):
        client.get_real_time_log_data_url(start_date=third_start_date, token=token, max_mb=max_mb)


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
        start_date = datetime.utcnow() - timedelta(seconds=session_faker.random.randint(1, 29))

        requested_url, _ = client.get_real_time_log_data_url(start_date=start_date)
        token = session_faker.word()

        mocked_responses.get(
            requested_url,
            status=401,
            body=logs_content.encode("utf-8"),
            headers={"X-sync-status": "done", "X-sync-token": token},
        )

        with pytest.raises(ValueError):
            await client.get_near_realtime_report(
                start_date=start_date,
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
        start_date = end_date - timedelta(seconds=session_faker.random.randint(1, 29))

        first_url, _ = client.get_real_time_log_data_url(start_date=start_date)
        token = session_faker.word()

        mocked_responses.get(
            first_url,
            status=200,
            body=logs_content.encode("utf-8"),
            headers={"X-sync-status": "done", "X-sync-token": token},
        )

        # Do not pass token
        result_file, _ = await client.get_near_realtime_report(
            start_date=start_date,
            token=None,
        )

        file_content = []

        async with aiofiles.open(result_file, encoding="utf-8") as file:
            async for line in file:
                file_content.append(line)

        await delete_file(result_file)

        assert "".join(file_content) == logs_content


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
        expected_start_date = datetime.now(pytz.utc) - timedelta(hours=2)
        input_token = session_faker.word()

        url, _ = client.get_real_time_log_data_url(start_date=expected_start_date, token=input_token)

        response_token = session_faker.word()

        mocked_responses.get(
            url,
            status=200,
            body=logs_content.encode("utf-8"),
            headers={"X-sync-status": "more", "X-sync-token": response_token},
        )

        # Do not pass token
        result_file, result_file_id = await client.get_near_realtime_report(
            start_date=None,
            token=input_token,
        )

        file_content = []

        async with aiofiles.open(result_file, encoding="utf-8") as file:
            async for line in file:
                file_content.append(line)

        await delete_file(result_file)

        assert "".join(file_content) == logs_content


@pytest.mark.asyncio
async def test_download_file_url(
    client: BroadcomCloudSwgClient,
    session_faker: Faker,
):
    url_1 = client.download_file_url(items=[1])
    url_2 = client.download_file_url(items=[1, 2, 3])

    assert url_1 == "{0}/reportpod/logs/download?type=hour&items=1&api".format(
        client.base_url,
    )

    assert url_2 == "{0}/reportpod/logs/download?type=hour&items=1,2,3&api".format(
        client.base_url,
    )


@pytest.mark.asyncio
async def test_list_of_files_url(
    client: BroadcomCloudSwgClient,
    session_faker: Faker,
):
    url_1 = client.download_file_url(items=[1])
    url_2 = client.download_file_url(items=[1, 2, 3])

    assert url_1 == "{0}/reportpod/logs/download?type=hour&items=1&api".format(
        client.base_url,
    )

    assert url_2 == "{0}/reportpod/logs/download?type=hour&items=1,2,3&api".format(
        client.base_url,
    )


@pytest.mark.asyncio
async def test_list_of_files(
    client: BroadcomCloudSwgClient,
    session_faker: Faker,
):
    with aioresponses() as mocked_responses:
        start_date = datetime.utcnow() - timedelta(hours=3)
        end_date = datetime.utcnow() - timedelta(hours=10)
        first_url = client.list_of_files_to_process_url(start_date, end_date)
        data = {
            session_faker.word(): session_faker.word(),
            session_faker.word(): session_faker.word(),
            session_faker.word(): session_faker.word(),
            session_faker.word(): session_faker.word(),
        }

        data1 = {
            session_faker.word(): session_faker.word(),
            session_faker.word(): session_faker.word(),
        }

        mocked_responses.get(
            first_url,
            status=200,
            payload=data,
        )

        result = await client.list_of_files(start_date, end_date)
        assert result == data

        second_start_date = datetime.now(pytz.utc) - timedelta(days=1)
        second_end_date = datetime.now(pytz.utc)
        mocked_responses.get(
            client.list_of_files_to_process_url(second_start_date, second_end_date), status=200, payload=data1
        )

        result1 = await client.list_of_files()
        assert result1 == data1


@pytest.mark.asyncio
async def test_parse_input_string():
    """Test parse_input_string method."""

    input_string = "value1 value2 value3"
    expected_output = {"field1": "value1", "field2": "value2", "field3": "value3"}
    result = BroadcomCloudSwgClient.parse_input_string(input_string, fields=["field1", "field2", "field3"])
    assert result == expected_output

    input_string = "value1 value2 value3 value4"
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

    input_string = "#Fields: field1 field2 field3"
    result = BroadcomCloudSwgClient.parse_string_as_headers(input_string)
    assert result == ["field1", "field2", "field3"]

    input_string = "#Fields: {0}".format(" ".join(BroadcomCloudSwgClient.full_list_of_elff_fields()))
    result = BroadcomCloudSwgClient.parse_string_as_headers(input_string)
    assert result == BroadcomCloudSwgClient.full_list_of_elff_fields()

    input_string = "value1 value2 value3"
    result = BroadcomCloudSwgClient.parse_string_as_headers(input_string)
    assert result is None

    input_string = "Fields: field1 field2 field3"
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


@pytest.mark.asyncio
async def test_parse_headers_and_values():
    """Test parse_string_as_headers method."""

    input_string = (
        "# Fields: x-bluecoat-request-tenant-id date time x-bluecoat-appliance-name time-taken c-ip cs-userdn "
        "cs-auth-groups x-exception-id sc-filter-result cs-categories cs(Referer) sc-status s-action cs-method rs("
        "Content-Type) cs-uri-scheme cs-host cs-uri-port cs-uri-path cs-uri-query cs-uri-extension cs(User-Agent) "
        "s-ip sc-bytes cs-bytes x-icap-reqmod-header(X-ICAP-Metadata) x-icap-respmod-header(X-ICAP-Metadata) "
        "x-data-leak-detected x-virus-id x-bluecoat-location-id x-bluecoat-location-name x-bluecoat-access-type "
        "x-bluecoat-application-name x-bluecoat-application-operation r-ip r-supplier-country "
        "x-rs-certificate-validate-status x-rs-certificate-observed-errors x-cs-ocsp-error x-rs-ocsp-error "
        "x-rs-connection-negotiated-ssl-version x-rs-connection-negotiated-cipher "
        "x-rs-connection-negotiated-cipher-size x-rs-certificate-hostname x-rs-certificate-hostname-categories "
        "x-cs-connection-negotiated-ssl-version x-cs-connection-negotiated-cipher "
        "x-cs-connection-negotiated-cipher-size x-cs-certificate-subject cs-icap-status cs-icap-error-details "
        "rs-icap-status rs-icap-error-details s-supplier-ip s-supplier-country s-supplier-failures "
        "x-cs-client-ip-country cs-threat-risk x-rs-certificate-hostname-threat-risk x-client-agent-type x-client-os "
        "x-client-agent-sw x-client-device-id x-client-device-name x-client-device-type "
        "x-client-security-posture-details x-client-security-posture-risk-score x-bluecoat-reference-id "
        "x-sc-connection-issuer-keyring x-sc-connection-issuer-keyring-alias x-cloud-rs x-bluecoat-placeholder cs("
        "X-Requested-With) x-random-ipv6 x-bluecoat-transaction-uuid"
    )

    input_1 = '18050 2023-01-22 05:05:41 "DP5-ACNSH2_ "kss_\ proxysg1" 80 1.2.3.4 ADSYSTRA\cyan - silent_denied DENIED "Technology/Internet" - 0 DENIED unknown - ssl test.com 443 / - - - 1.2.3.4 0 1632 - - - - 0 "client" client_connector - - 1.2.3.4 "Singapore" CERT_VALID none - - TLSv1.2 ECDHE-RSA *.wns.windows.com Technology/Internet TLSv1.2 ECDHE-RSA - ICAP_NOT_SCANNED - ICAP_NOT_SCANNED - - Singapore - "Test" 2 2 wss-agent architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044 9.1.2.19354 5b8a0e41-7212-4dae-8cd8-2ae211f642e3 DWPCNSZ22032 - - - - SSL_Intercept_1 - - - - test'
    input_2 = '18050 2023-01-22 05:07:12 "DP5-ACNSH2_proxysg1" 82 1.2.3.4 ADSYSTRA\cyan - silent_denied DENIED "Technology/Internet" - 0 DENIED unknown - ssl test.com 443 / - - - 1.2.3.4 0 1632 - - - - 0 "client" client_connector - - 1.2.3.4 "Singapore" CERT_VALID none - - TLSv1.2 ECDHE-RSA *.wns.windows.com Technology/Internet TLSv1.2 ECDHE-RSA - ICAP_NOT_SCANNED - ICAP_NOT_SCANNED - - Singapore - "Test" 2 2 wss-agent architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044 9.1.2.19354 5b8a0e41-7212-4dae-8cd8-2ae211f642e3 DWPCNSZ22032 - - - - SSL_Intercept_1 - - - - test'
    input_3 = '18050 2023-01-22 05:01:04 "DP3-ACNSH2_proxysg1" 85 1.2.3.4 ADSYSTRA\jliu1 - silent_denied DENIED "Technology/Internet" - 0 DENIED unknown - ssl test.com 443 / - - - 1.2.3.4 0 1632 - - - - 0 "client" client_connector - - 1.2.3.4 "Singapore" CERT_VALID none - - TLSv1.2 ECDHE-RSA *.wns.windows.com Technology/Internet TLSv1.2 ECDHE-RSA - ICAP_NOT_SCANNED - ICAP_NOT_SCANNED - - Singapore - "Test" 2 2 wss-agent architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044 9.1.2.19354 3de1cf18-68d9-450c-9893-82235790e758 DWPCNSZ22009 PC - - - SSL_Intercept_1 - - - - test'

    expected_headers = [
        "x-bluecoat-request-tenant-id",
        "date",
        "time",
        "x-bluecoat-appliance-name",
        "time-taken",
        "c-ip",
        "cs-userdn",
        "cs-auth-groups",
        "x-exception-id",
        "sc-filter-result",
        "cs-categories",
        "cs(Referer)",
        "sc-status",
        "s-action",
        "cs-method",
        "rs(Content-Type)",
        "cs-uri-scheme",
        "cs-host",
        "cs-uri-port",
        "cs-uri-path",
        "cs-uri-query",
        "cs-uri-extension",
        "cs(User-Agent)",
        "s-ip",
        "sc-bytes",
        "cs-bytes",
        "x-icap-reqmod-header(X-ICAP-Metadata)",
        "x-icap-respmod-header(X-ICAP-Metadata)",
        "x-data-leak-detected",
        "x-virus-id",
        "x-bluecoat-location-id",
        "x-bluecoat-location-name",
        "x-bluecoat-access-type",
        "x-bluecoat-application-name",
        "x-bluecoat-application-operation",
        "r-ip",
        "r-supplier-country",
        "x-rs-certificate-validate-status",
        "x-rs-certificate-observed-errors",
        "x-cs-ocsp-error",
        "x-rs-ocsp-error",
        "x-rs-connection-negotiated-ssl-version",
        "x-rs-connection-negotiated-cipher",
        "x-rs-connection-negotiated-cipher-size",
        "x-rs-certificate-hostname",
        "x-rs-certificate-hostname-categories",
        "x-cs-connection-negotiated-ssl-version",
        "x-cs-connection-negotiated-cipher",
        "x-cs-connection-negotiated-cipher-size",
        "x-cs-certificate-subject",
        "cs-icap-status",
        "cs-icap-error-details",
        "rs-icap-status",
        "rs-icap-error-details",
        "s-supplier-ip",
        "s-supplier-country",
        "s-supplier-failures",
        "x-cs-client-ip-country",
        "cs-threat-risk",
        "x-rs-certificate-hostname-threat-risk",
        "x-client-agent-type",
        "x-client-os",
        "x-client-agent-sw",
        "x-client-device-id",
        "x-client-device-name",
        "x-client-device-type",
        "x-client-security-posture-details",
        "x-client-security-posture-risk-score",
        "x-bluecoat-reference-id",
        "x-sc-connection-issuer-keyring",
        "x-sc-connection-issuer-keyring-alias",
        "x-cloud-rs",
        "x-bluecoat-placeholder",
        "cs(X-Requested-With)",
        "x-random-ipv6",
        "x-bluecoat-transaction-uuid",
    ]

    expected_parsed1 = {
        "c-ip": "1.2.3.4",
        "cs-bytes": "1632",
        "cs-categories": "Technology/Internet",
        "cs-host": "test.com",
        "cs-icap-status": "ICAP_NOT_SCANNED",
        "cs-method": "unknown",
        "cs-threat-risk": "wss-agent",
        "cs-uri-path": "/",
        "cs-uri-port": "443",
        "cs-uri-scheme": "ssl",
        "cs-userdn": "ADSYSTRA\\cyan",
        "date": "2023-01-22",
        "r-ip": "1.2.3.4",
        "r-supplier-country": "Singapore",
        "rs-icap-error-details": "Singapore",
        "s-action": "DENIED",
        "s-ip": "1.2.3.4",
        "s-supplier-country": "Test",
        "s-supplier-failures": "2",
        "sc-bytes": "0",
        "sc-filter-result": "DENIED",
        "sc-status": "0",
        "time": "05:05:41",
        "time-taken": "80",
        "x-bluecoat-access-type": "client_connector",
        "x-bluecoat-appliance-name": 'DP5-ACNSH2_ "kss_\\ proxysg1',
        "x-bluecoat-location-id": "0",
        "x-bluecoat-location-name": "client",
        "x-bluecoat-placeholder": "test",
        "x-bluecoat-request-tenant-id": "18050",
        "x-client-agent-sw": "DWPCNSZ22032",
        "x-client-agent-type": "9.1.2.19354",
        "x-client-os": "5b8a0e41-7212-4dae-8cd8-2ae211f642e3",
        "x-client-security-posture-risk-score": "SSL_Intercept_1",
        "x-cs-client-ip-country": "2",
        "x-cs-connection-negotiated-cipher-size": "ICAP_NOT_SCANNED",
        "x-cs-connection-negotiated-ssl-version": "ECDHE-RSA",
        "x-exception-id": "silent_denied",
        "x-rs-certificate-hostname": "Technology/Internet",
        "x-rs-certificate-hostname-categories": "TLSv1.2",
        "x-rs-certificate-hostname-threat-risk": "architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044",
        "x-rs-certificate-observed-errors": "none",
        "x-rs-certificate-validate-status": "CERT_VALID",
        "x-rs-connection-negotiated-cipher": "ECDHE-RSA",
        "x-rs-connection-negotiated-cipher-size": "*.wns.windows.com",
        "x-rs-connection-negotiated-ssl-version": "TLSv1.2",
    }

    expected_parsed2 = {
        "x-bluecoat-request-tenant-id": "18050",
        "date": "2023-01-22",
        "time": "05:07:12",
        "x-bluecoat-appliance-name": "DP5-ACNSH2_proxysg1",
        "time-taken": "82",
        "c-ip": "1.2.3.4",
        "cs-userdn": "ADSYSTRA\\cyan",
        "x-exception-id": "silent_denied",
        "sc-filter-result": "DENIED",
        "cs-categories": "Technology/Internet",
        "sc-status": "0",
        "s-action": "DENIED",
        "cs-method": "unknown",
        "cs-uri-scheme": "ssl",
        "cs-host": "test.com",
        "cs-uri-port": "443",
        "cs-uri-path": "/",
        "s-ip": "1.2.3.4",
        "sc-bytes": "0",
        "cs-bytes": "1632",
        "x-bluecoat-location-id": "0",
        "x-bluecoat-location-name": "client",
        "x-bluecoat-access-type": "client_connector",
        "r-ip": "1.2.3.4",
        "r-supplier-country": "Singapore",
        "x-rs-certificate-validate-status": "CERT_VALID",
        "x-rs-certificate-observed-errors": "none",
        "x-rs-connection-negotiated-ssl-version": "TLSv1.2",
        "x-rs-connection-negotiated-cipher": "ECDHE-RSA",
        "x-rs-connection-negotiated-cipher-size": "*.wns.windows.com",
        "x-rs-certificate-hostname": "Technology/Internet",
        "x-rs-certificate-hostname-categories": "TLSv1.2",
        "x-cs-connection-negotiated-ssl-version": "ECDHE-RSA",
        "x-cs-connection-negotiated-cipher-size": "ICAP_NOT_SCANNED",
        "cs-icap-status": "ICAP_NOT_SCANNED",
        "rs-icap-error-details": "Singapore",
        "s-supplier-country": "Test",
        "s-supplier-failures": "2",
        "x-cs-client-ip-country": "2",
        "cs-threat-risk": "wss-agent",
        "x-rs-certificate-hostname-threat-risk": "architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044",
        "x-client-agent-type": "9.1.2.19354",
        "x-client-os": "5b8a0e41-7212-4dae-8cd8-2ae211f642e3",
        "x-client-agent-sw": "DWPCNSZ22032",
        "x-client-security-posture-risk-score": "SSL_Intercept_1",
        "x-bluecoat-placeholder": "test",
    }

    expected_parsed3 = {
        "x-bluecoat-request-tenant-id": "18050",
        "date": "2023-01-22",
        "time": "05:01:04",
        "x-bluecoat-appliance-name": "DP3-ACNSH2_proxysg1",
        "time-taken": "85",
        "c-ip": "1.2.3.4",
        "cs-userdn": "ADSYSTRA\\jliu1",
        "x-exception-id": "silent_denied",
        "sc-filter-result": "DENIED",
        "cs-categories": "Technology/Internet",
        "sc-status": "0",
        "s-action": "DENIED",
        "cs-method": "unknown",
        "cs-uri-scheme": "ssl",
        "cs-host": "test.com",
        "cs-uri-port": "443",
        "cs-uri-path": "/",
        "s-ip": "1.2.3.4",
        "sc-bytes": "0",
        "cs-bytes": "1632",
        "x-bluecoat-location-id": "0",
        "x-bluecoat-location-name": "client",
        "x-bluecoat-access-type": "client_connector",
        "r-ip": "1.2.3.4",
        "r-supplier-country": "Singapore",
        "x-rs-certificate-validate-status": "CERT_VALID",
        "x-rs-certificate-observed-errors": "none",
        "x-rs-connection-negotiated-ssl-version": "TLSv1.2",
        "x-rs-connection-negotiated-cipher": "ECDHE-RSA",
        "x-rs-connection-negotiated-cipher-size": "*.wns.windows.com",
        "x-rs-certificate-hostname": "Technology/Internet",
        "x-rs-certificate-hostname-categories": "TLSv1.2",
        "x-cs-connection-negotiated-ssl-version": "ECDHE-RSA",
        "x-cs-connection-negotiated-cipher-size": "ICAP_NOT_SCANNED",
        "cs-icap-status": "ICAP_NOT_SCANNED",
        "rs-icap-error-details": "Singapore",
        "s-supplier-country": "Test",
        "s-supplier-failures": "2",
        "x-cs-client-ip-country": "2",
        "cs-threat-risk": "wss-agent",
        "x-rs-certificate-hostname-threat-risk": "architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044",
        "x-client-agent-type": "9.1.2.19354",
        "x-client-os": "3de1cf18-68d9-450c-9893-82235790e758",
        "x-client-agent-sw": "DWPCNSZ22009",
        "x-client-device-id": "PC",
        "x-client-security-posture-risk-score": "SSL_Intercept_1",
        "x-bluecoat-placeholder": "test",
    }

    assert BroadcomCloudSwgClient.parse_string_as_headers(input_string) == expected_headers
    assert BroadcomCloudSwgClient.parse_input_string(input_1, expected_headers) == expected_parsed1
    assert BroadcomCloudSwgClient.parse_input_string(input_2, expected_headers) == expected_parsed2
    assert BroadcomCloudSwgClient.parse_input_string(input_3, expected_headers) == expected_parsed3
