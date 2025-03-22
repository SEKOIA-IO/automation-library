"""Tests related to AwsS3LogsTrigger."""

import json
from pathlib import Path


import pytest
from faker import Faker

from connectors import AwsModule
from connectors.s3.trigger_s3_cloudfront import AwsS3CloudFrontConfiguration, AwsS3CloudFrontTrigger
from tests.helpers import async_list, async_temporary_file


@pytest.fixture
def test_data_3_1() -> bytes:
    return """
#Version: 1.0\n#Fields: date time x-edge-location sc-bytes c-ip cs-method cs(Host) cs-uri-stem sc-status cs(Referer) cs(User-Agent) cs-uri-query cs(Cookie) x-edge-result-type x-edge-request-id x-host-header cs-protocol cs-bytes time-taken x-forwarded-for ssl-protocol ssl-cipher x-edge-response-result-type cs-protocol-version fle-status fle-encrypted-fields c-port time-to-first-byte x-edge-detailed-result-type sc-content-type sc-content-len sc-range-start sc-range-end\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n
""".encode(
        "utf-8"
    )


@pytest.fixture
def test_data_2_2() -> bytes:
    return """
#Version: 1.0\n#Fields: date time x-edge-location sc-bytes c-ip cs-method cs(Host) cs-uri-stem sc-status cs(Referer) cs(User-Agent) cs-uri-query cs(Cookie) x-edge-result-type x-edge-request-id x-host-header cs-protocol cs-bytes time-taken x-forwarded-for ssl-protocol ssl-cipher x-edge-response-result-type cs-protocol-version fle-status fle-encrypted-fields c-port time-to-first-byte x-edge-detailed-result-type sc-content-type sc-content-len sc-range-start sc-range-end\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-13-05\t20:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-
""".encode(
        "utf-8"
    )


@pytest.fixture
def test_data_1_1() -> bytes:
    return """
#Version: 1.0\n#Fields: date time x-edge-location sc-bytes c-ip cs-method cs(Host) cs-uri-stem sc-status cs(Referer) cs(User-Agent) cs-uri-query cs(Cookie) x-edge-result-type x-edge-request-id x-host-header cs-protocol cs-bytes time-taken x-forwarded-for ssl-protocol ssl-cipher x-edge-response-result-type cs-protocol-version fle-status fle-encrypted-fields c-port time-to-first-byte x-edge-detailed-result-type sc-content-type sc-content-len sc-range-start sc-range-end\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-
""".encode(
        "utf-8"
    )


@pytest.fixture
def test_data_3_2_2() -> bytes:
    return """
#Version: 1.0\n#Fields: date time x-edge-location sc-bytes c-ip cs-method cs(Host) cs-uri-stem sc-status cs(Referer) cs(User-Agent) cs-uri-query cs(Cookie) x-edge-result-type x-edge-request-id x-host-header cs-protocol cs-bytes time-taken x-forwarded-for ssl-protocol ssl-cipher x-edge-response-result-type cs-protocol-version fle-status fle-encrypted-fields c-port time-to-first-byte x-edge-detailed-result-type sc-content-type sc-content-len sc-range-start sc-range-end\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-13-05\t20:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-13-05\t20:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-
""".encode(
        "utf-8"
    )


@pytest.fixture
def test_data_3_2_1_3() -> bytes:
    return """
#Version: 1.0\n#Fields: date time x-edge-location sc-bytes c-ip cs-method cs(Host) cs-uri-stem sc-status cs(Referer) cs(User-Agent) cs-uri-query cs(Cookie) x-edge-result-type x-edge-request-id x-host-header cs-protocol cs-bytes time-taken x-forwarded-for ssl-protocol ssl-cipher x-edge-response-result-type cs-protocol-version fle-status fle-encrypted-fields c-port time-to-first-byte x-edge-detailed-result-type sc-content-type sc-content-len sc-range-start sc-range-end\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-12-05\t16:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-13-05\t20:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-13-05\t20:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tMiss\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tMiss\tHTTP/2.0\t-\t-\t58623\t0.358\tMiss\ttext/html;%20charset=UTF-8\t0\t-\t-\n2023-25-05\t20:15:33\ttest-P1\t484\t0000:111:222:3333:4444:5555:6666:7777\tGET\ttest.cloudfront.net\t/\t302\t-\tMozilla/5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2030_17_5)%20AppleWebKit/60.1.15%20(KHTML,%20like%20Gecko)%20Version/17.1%20Safari/605.1.15\t-\t-\tRefresh\tnaq21Gsr0URELHa3erNtE0FoUUXDw16HXgISOWLclFzk==\ttest1.cloudfront.net\thttps\t258\t0.358\t-\tTLSv1.3\tTLS_AES_128_GCM_SHA256\tRefresh\tHTTP/2.0\t-\t-\t58623\t0.358\tRefresh\ttext/html;%20charset=UTF-8\t0\t-\t-
""".encode(
        "utf-8"
    )


@pytest.fixture
def aws_s3_cloudfront_trigger_config(faker: Faker) -> AwsS3CloudFrontConfiguration:
    config = {
        "frequency": 0,
        "queue_name": faker.word(),
        "separator": "\n",
        "skip_first": 0,
        "ignore_comments": False,
        "intake_key": faker.word(),
    }

    return AwsS3CloudFrontConfiguration(**config)


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_cloudfront_trigger_config: AwsS3CloudFrontConfiguration,
) -> AwsS3CloudFrontTrigger:
    connector = AwsS3CloudFrontTrigger(module=aws_module, data_path=symphony_storage)

    connector.module = aws_module
    connector.configuration = aws_s3_cloudfront_trigger_config

    return connector


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_data(connector: AwsS3CloudFrontTrigger, test_data_3_1: bytes):
    async with async_temporary_file(test_data_3_1) as stream:
        decoded_records = [json.loads(record) async for record in connector._parse_content(stream)]

        assert len(decoded_records) == 1
        assert decoded_records[0]["start_time"]
        assert decoded_records[0]["end_time"]
        assert decoded_records[0]["count"] == 3


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_data_3_2_2(connector: AwsS3CloudFrontTrigger, test_data_3_2_2: bytes):
    async with async_temporary_file(test_data_3_2_2) as stream:
        decoded_records = [json.loads(record) async for record in connector._parse_content(stream)]

        assert len(decoded_records) == 2
        assert decoded_records[0]["start_time"]
        assert decoded_records[0]["end_time"]
        assert decoded_records[0]["count"] == 3
        assert decoded_records[1]["count"] == 2


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_data_2_2(connector: AwsS3CloudFrontTrigger, test_data_2_2: bytes):
    async with async_temporary_file(test_data_2_2) as stream:
        decoded_records = [json.loads(record) async for record in connector._parse_content(stream)]

        assert len(decoded_records) == 2
        assert decoded_records[0]["start_time"]
        assert decoded_records[0]["end_time"]
        assert decoded_records[0]["count"] == 1


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_data_1_1(connector: AwsS3CloudFrontTrigger, test_data_1_1: bytes):
    async with async_temporary_file(test_data_1_1) as stream:
        decoded_records = [json.loads(record) async for record in connector._parse_content(stream)]

        assert len(decoded_records) == 1
        assert decoded_records[0]["start_time"]
        assert decoded_records[0]["end_time"]
        assert decoded_records[0]["count"] == 1


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_data_3_2_1_3(connector: AwsS3CloudFrontTrigger, test_data_3_2_1_3: bytes):
    async with async_temporary_file(test_data_3_2_1_3) as stream:
        decoded_records = [json.loads(record) async for record in connector._parse_content(stream)]

        assert len(decoded_records) == 3
        assert decoded_records[0]["start_time"]
        assert decoded_records[0]["end_time"]
        assert decoded_records[0]["count"] == 3
        assert decoded_records[1]["count"] == 2
        assert decoded_records[2]["count"] == 1


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_without_records(connector: AwsS3CloudFrontTrigger):
    async with async_temporary_file(b"") as f:
        assert await async_list(connector._parse_content(f)) == []
