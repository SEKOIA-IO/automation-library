from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aioresponses import aioresponses
from faker import Faker

from client.http_client import BitsightClient
from connectors import BitsightModule, BitsightModuleConfiguration
from connectors.pull_findings_trigger import Checkpoint, CompanyCheckpoint, PullFindingsConnector


@pytest.fixture
def company_uuids(session_faker: Faker) -> list[str]:
    """
    Create company uuids.

    Args:
        session_faker: Faker
    """
    return [session_faker.word() for _ in range(10)]


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
def connector(
    symphony_storage: Path, session_faker: Faker, company_uuids: list[str], mock_push_data_to_intakes: AsyncMock
) -> PullFindingsConnector:
    """
    Create a PullFindingsConnector instance.

    Args:
        symphony_storage: Path
        session_faker: Faker
        company_uuids: list[str]
        mock_push_data_to_intakes: AsyncMock

    Returns:
        PullFindingsConnector:
    """
    module = BitsightModule()
    connector = PullFindingsConnector(module=module, data_path=symphony_storage)

    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    connector.push_data_to_intakes = mock_push_data_to_intakes

    connector.module.configuration = BitsightModuleConfiguration(
        **{
            "api_token": session_faker.word(),
            "company_uuids": company_uuids,
        }
    )

    connector.configuration = {
        "intake_server": session_faker.uri(),
        "intake_key": session_faker.word(),
    }

    return connector


def new_finding(last_seen: str, session_faker: Faker) -> dict:
    return {
        **session_faker.pydict(allowed_types=[str, int]),
        "last_seen": last_seen,
        "assets": [session_faker.word(), session_faker.word()],
        "details": {
            "vulnerabilities": [session_faker.word(), session_faker.word(), session_faker.word()],
            **session_faker.pydict(allowed_types=[str, int]),
        },
    }


@pytest.mark.asyncio
async def test_pull_findings_connector_format_finding(connector: PullFindingsConnector, session_faker: Faker):
    """
    Test PullFindingsConnector.format_finding.

    Args:
        connector: PullFindingsConnector
        session_faker: Faker
    """
    company_uuid = session_faker.word()
    simple_finding = session_faker.pydict(allowed_types=[str, int])
    assets = [session_faker.word(), session_faker.word()]
    vulnerabilities = [session_faker.word(), session_faker.word()]
    details = session_faker.pydict(allowed_types=[str, int])

    assert PullFindingsConnector.format_finding(simple_finding, company_uuid) == []

    finding_2 = {"assets": assets, **simple_finding}
    assert PullFindingsConnector.format_finding(finding_2, company_uuid) == [
        {**simple_finding, "company_uuid": company_uuid, "asset": assets[0], "details": {}},
        {**simple_finding, "company_uuid": company_uuid, "asset": assets[1], "details": {}},
    ]

    finding_3 = {"assets": assets, "details": {"vulnerabilities": vulnerabilities, **details}, **simple_finding}
    assert PullFindingsConnector.format_finding(finding_3, company_uuid) == [
        {
            **simple_finding,
            "company_uuid": company_uuid,
            "asset": assets[0],
            "vulnerability": vulnerabilities[0],
            "details": details,
        },
        {
            **simple_finding,
            "company_uuid": company_uuid,
            "asset": assets[0],
            "vulnerability": vulnerabilities[1],
            "details": details,
        },
        {
            **simple_finding,
            "company_uuid": company_uuid,
            "asset": assets[1],
            "vulnerability": vulnerabilities[0],
            "details": details,
        },
        {
            **simple_finding,
            "company_uuid": company_uuid,
            "asset": assets[1],
            "vulnerability": vulnerabilities[1],
            "details": details,
        },
    ]


@pytest.mark.asyncio
async def test_pull_findings_connector_process_findings_for_company_1(
    connector: PullFindingsConnector, session_faker: Faker
):
    """
    Test PullFindingsConnector.process_findings_for_company with findings.

    Args:
        connector: PullFindingsConnector
        session_faker: Faker
    """
    company_id = session_faker.word()

    now = datetime.utcnow().replace(microsecond=0, second=0, minute=0, hour=0)
    now_minus_1_day = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    now_minus_1_minute = (now - timedelta(minutes=1)).isoformat()
    findings_1 = [new_finding(now_minus_1_minute, session_faker) for _ in range(10)]
    next_url_1 = session_faker.uri()

    now_minus_5_minute = (now - timedelta(minutes=5)).isoformat()
    findings_2 = [new_finding(now_minus_5_minute, session_faker) for _ in range(10)]
    next_url_2 = session_faker.uri()

    now_minus_10_minute = (now - timedelta(minutes=10)).isoformat()
    findings_3 = [new_finding(now_minus_10_minute, session_faker) for _ in range(10)]

    with aioresponses() as mocked_responses:
        mocked_responses.get(
            next_url_2,
            payload={"results": findings_3},
            repeat=True,
        )

        mocked_responses.get(
            next_url_1,
            payload={"links": {"next": next_url_2}, "results": findings_2},
            repeat=True,
        )

        checkpoint = connector.get_checkpoint()

        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings?last_seen={now_minus_1_day}",
            payload={"links": {"next": next_url_1}, "results": findings_1},
            repeat=True,
        )

        result = await connector.process_findings_for_company(checkpoint, company_id)

        # result should contain findings from all 3 pages and a None value
        assert result == 180


@pytest.mark.asyncio
async def test_pull_findings_connector_next_batch(connector: PullFindingsConnector, session_faker: Faker):
    """
    Test PullFindingsConnector.next_batch with findings.

    It is complex test for entire workflow.
    We will work with 2 companies, each company will have 2 pages of findings.
    Each finding will have 2 assets and 3 vulnerabilities.

    Args:
        connector: PullFindingsConnector
        session_faker: Faker
    """
    now = datetime.utcnow().replace(microsecond=0, second=0, minute=0, hour=0)

    now_minus_1_day = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    date_1 = (now - timedelta(days=1)).isoformat()
    findings_1 = [new_finding(date_1, session_faker) for _ in range(3)]

    date_2 = (now - timedelta(minutes=5)).isoformat()
    findings_2 = [new_finding(date_2, session_faker) for _ in range(4)]

    with aioresponses() as mocked_responses:
        # Mock requests to company #1
        company_id_1: str = session_faker.word()
        next_url_1 = session_faker.uri()

        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id_1}/findings?last_seen={now_minus_1_day}",
            payload={"links": {"next": next_url_1}, "results": findings_1},
            repeat=True,
        )

        mocked_responses.get(next_url_1, payload={"results": findings_2}, repeat=True)

        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id_1}/findings?last_seen={now.isoformat()}",
            payload={"links": {"next": next_url_1}, "results": []},
            repeat=True,
        )

        # Mock requests to company #2
        company_id_2: str = session_faker.word()
        next_url_2 = session_faker.uri()
        offset_company_2 = 123

        mocked_responses.get(
            BitsightClient.get_url(company_id_2, last_seen=date_1, offset=offset_company_2),
            payload={"links": {"next": next_url_2}, "results": findings_1},
            repeat=True,
        )
        mocked_responses.get(next_url_2, payload={"results": findings_2}, repeat=True)

        connector.configuration.batch_limit = 1
        connector.module.configuration.company_uuids = [company_id_1, company_id_2]

        start_checkpoint = Checkpoint(
            values=[
                CompanyCheckpoint(
                    company_uuid=company_id_2,
                    last_seen=date_1,
                    offset=offset_company_2,
                )
            ]
        )

        connector.save_checkpoint(start_checkpoint)

        result, finish_checkpoint = await connector.next_batch()

        one_company_events = (len(findings_1) + len(findings_2)) * 2 * 3
        assert result == one_company_events * 2
        assert (
            finish_checkpoint
            == Checkpoint(
                values=[
                    CompanyCheckpoint(company_uuid=company_id_1, last_seen=now.strftime("%Y-%m-%d"), offset=1),
                    CompanyCheckpoint(company_uuid=company_id_2, last_seen=now.strftime("%Y-%m-%d"), offset=1),
                ]
            ).dict()
        )

        assert connector.get_checkpoint().dict() == finish_checkpoint.dict()
