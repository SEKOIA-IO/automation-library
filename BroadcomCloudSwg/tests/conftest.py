"""Additional programmatic configuration for pytest."""

import asyncio
import datetime
import random
from typing import List

import pytest
from faker import Faker

from client.broadcom_cloud_swg_client import BroadcomCloudSwgClient


@pytest.fixture(scope="session")
def faker_locale() -> List[str]:
    """
    Configure Faker to use correct locale.

    Returns:
        List[str]:
    """
    return ["en"]


@pytest.fixture(scope="session")
def faker_seed() -> int:
    """
    Configure Faker to use correct seed.

    Returns:
        int:
    """
    return random.randint(1, 10000)


@pytest.fixture(scope="session")
def session_faker(faker_locale: List[str], faker_seed: int) -> Faker:
    """
    Configure session lvl Faker to use correct seed and locale.

    Args:
        faker_locale: List[str]
        faker_seed: int

    Returns:
        Faker:
    """
    instance = Faker(locale=faker_locale)
    instance.seed_instance(seed=faker_seed)

    return instance


@pytest.fixture
def logs_content(session_faker) -> str:
    """
    Generate logs content.

    Args:
        session_faker: Faker
    """
    number_of_rows = session_faker.random.randint(1, 50)

    # 3 fields in logs
    rows = [
        " ".join(
            [
                session_faker.past_datetime(datetime.datetime.utcnow()).strftime(BroadcomCloudSwgClient._time_format),
                session_faker.word(),
                session_faker.word(),
            ]
        )
        for _ in range(number_of_rows)
    ]

    headers = "\n".join(
        [
            "#Version: 1.0",
            "#Date: 12-Jan-1996 00:00:00",
            "#Fields: time cs-method s-action",
        ]
    )

    return headers + "\n" + "\n".join(rows)


@pytest.fixture
def logs_complete_content(session_faker) -> str:
    return "\n".join(
        [
            "# Version: 1.0",
            "# Date: 2023-01-22T05",
            "# Software: EAR 2.6",
            "# Start-Date: 2023-01-22 05:05:41",
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
            "X-Requested-With) x-random-ipv6 x-bluecoat-transaction-uuid",
            '18050 2023-01-22 05:05:41 "DP5-ACNSH2_ "kss_\ proxysg1" 80 1.2.3.4 ADSYSTRA\cyan - silent_denied DENIED "Technology/Internet" - 0 DENIED unknown - ssl test.com 443 / - - - 1.2.3.4 0 1632 - - - - 0 "client" client_connector - - 1.2.3.4 "Singapore" CERT_VALID none - - TLSv1.2 ECDHE-RSA *.wns.windows.com Technology/Internet TLSv1.2 ECDHE-RSA - ICAP_NOT_SCANNED - ICAP_NOT_SCANNED - - Singapore - "Test" 2 2 wss-agent architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044 9.1.2.19354 5b8a0e41-7212-4dae-8cd8-2ae211f642e3 DWPCNSZ22032 - - - - SSL_Intercept_1 - - - - test',
            '18050 2023-01-22 05:07:12 "DP5-ACNSH2_proxysg1" 82 1.2.3.4 ADSYSTRA\cyan - silent_denied DENIED "Technology/Internet" - 0 DENIED unknown - ssl test.com 443 / - - - 1.2.3.4 0 1632 - - - - 0 "client" client_connector - - 1.2.3.4 "Singapore" CERT_VALID none - - TLSv1.2 ECDHE-RSA *.wns.windows.com Technology/Internet TLSv1.2 ECDHE-RSA - ICAP_NOT_SCANNED - ICAP_NOT_SCANNED - - Singapore - "Test" 2 2 wss-agent architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044 9.1.2.19354 5b8a0e41-7212-4dae-8cd8-2ae211f642e3 DWPCNSZ22032 - - - - SSL_Intercept_1 - - - - test',
            '18050 2023-01-22 05:01:04 "DP3-ACNSH2_proxysg1" 85 1.2.3.4 ADSYSTRA\jliu1 - silent_denied DENIED "Technology/Internet" - 0 DENIED unknown - ssl test.com 443 / - - - 1.2.3.4 0 1632 - - - - 0 "client" client_connector - - 1.2.3.4 "Singapore" CERT_VALID none - - TLSv1.2 ECDHE-RSA *.wns.windows.com Technology/Internet TLSv1.2 ECDHE-RSA - ICAP_NOT_SCANNED - ICAP_NOT_SCANNED - - Singapore - "Test" 2 2 wss-agent architecture=x86_64%20name=Windows%2010%20Enterprise%20version=10.0.19044 9.1.2.19354 3de1cf18-68d9-450c-9893-82235790e758 DWPCNSZ22009 PC - - - SSL_Intercept_1 - - - - test',
        ]
    )


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for pytest.mark.asyncio.

    Yields:
        loop:
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()

    yield loop

    loop.close()
