import asyncio
import random
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from types import SimpleNamespace
from typing import List
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from msgraph.generated.models.audit_activity_initiator import AuditActivityInitiator
from msgraph.generated.models.directory_audit import DirectoryAudit
from msgraph.generated.models.sign_in import SignIn
from msgraph.generated.models.sign_in_status import SignInStatus
from msgraph.generated.models.user_identity import UserIdentity
from sekoia_automation import constants

from graph_api.client import GraphApi


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


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


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for pytest.mark.asyncio.

    Yields:
        loop:
    """
    loop = asyncio.get_event_loop()

    yield loop

    loop.close()


@pytest.fixture
def mock_push_data_to_intakes() -> AsyncMock:
    """
    Mocked push_data_to_intakes method.

    Returns:
        AsyncMock:
    """

    def side_effect_return_input(events: list[str]) -> list[str]:
        """
        Return input value.

        Uses in side_effect to return input value from mocked function.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        return events

    return AsyncMock(side_effect=side_effect_return_input)


@pytest.fixture
def graph_api_client(session_faker: Faker) -> GraphApi:
    client = GraphApi(
        tenant_id=session_faker.word(),
        client_id=session_faker.word(),
        client_secret=session_faker.word(),
    )

    client_mock = MagicMock(name="GraphServiceClient")
    client_mock.audit_logs = MagicMock(name="AuditLogs")

    # Sign-ins builder
    sign_ins = MagicMock(name="SignInsRequestBuilder")
    sign_ins.get = AsyncMock()
    sign_ins.with_url = MagicMock()
    sign_ins.with_url.return_value.get = AsyncMock()
    client_mock.audit_logs.sign_ins = sign_ins

    # Directory audits builder
    dir_audits = MagicMock(name="DirectoryAuditsRequestBuilder")
    dir_audits.get = AsyncMock()
    dir_audits.with_url = MagicMock()
    dir_audits.with_url.return_value.get = AsyncMock()
    client_mock.audit_logs.directory_audits = dir_audits

    client._credentials = MagicMock()
    client._client = client_mock

    return client


@pytest.fixture
def signins_page_1() -> SimpleNamespace:
    next_link = "https://graph.microsoft.com/v1.0/auditLogs/signIns?$skiptoken=abc123"

    return SimpleNamespace(
        value=[
            SignIn(
                id="0",
                created_date_time=datetime.fromisoformat("2025-09-01T01:00:00Z"),
                user_principal_name="u1@example.com",
                ip_address="1.1.1.1",
                status=SignInStatus(error_code=0),
            ),
            SignIn(
                id="1",
                created_date_time=datetime.fromisoformat("2025-09-01T01:00:00Z"),
                user_principal_name="u1@example.com",
                ip_address="1.1.1.1",
                status=SignInStatus(error_code=0),
            ),
        ],
        odata_next_link=next_link,
    )


@pytest.fixture
def signins_page_2() -> SimpleNamespace:
    return SimpleNamespace(
        value=[
            SignIn(
                id="2",
                created_date_time=datetime.fromisoformat("2025-09-01T01:00:00Z"),
                user_principal_name="u2@example.com",
                ip_address="2.2.2.2",
                status=SignInStatus(error_code=0),
            )
        ],
        odata_next_link=None,
    )


@pytest.fixture
def directory_audits_page_1() -> SimpleNamespace:
    next_link = "https://graph.microsoft.com/v1.0/auditLogs/directoryAudits?$skiptoken=abc123"

    return SimpleNamespace(
        value=[
            DirectoryAudit(
                id="3",
                activity_date_time=datetime.fromisoformat("2025-09-01T00:00:00Z"),
                activity_display_name="Add user",
                initiated_by=AuditActivityInitiator(user=UserIdentity(display_name="Admin")),
            )
        ],
        odata_next_link=next_link,
    )


@pytest.fixture
def directory_audits_page_2() -> SimpleNamespace:
    return SimpleNamespace(
        value=[
            DirectoryAudit(
                id="4",
                activity_date_time=datetime.fromisoformat("2025-09-01T01:00:00Z"),
                activity_display_name="Delete user",
                initiated_by=AuditActivityInitiator(user=UserIdentity(display_name="Admin2")),
            ),
            DirectoryAudit(
                id="5",
                activity_date_time=datetime.fromisoformat("2025-09-01T01:00:00Z"),
                activity_display_name="Delete user",
                initiated_by=AuditActivityInitiator(user=UserIdentity(display_name="Admin2")),
            ),
        ],
        odata_next_link=None,
    )
