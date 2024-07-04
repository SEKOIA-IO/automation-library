from asyncio import Queue
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aioresponses import aioresponses
from faker import Faker

from client.http_client import BitsightClient
from connectors import BitsightModule, BitsightModuleConfiguration
from connectors.pull_findings_trigger import Checkpoint, CompanyCheckpoint, FindingQueue, PullFindingsConnector


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
    queue: FindingQueue = Queue()

    findings_1 = [session_faker.pydict(allowed_types=[str, int]) for _ in range(10)]
    next_url_1 = session_faker.uri()

    findings_2 = [session_faker.pydict(allowed_types=[str, int]) for _ in range(10)]
    next_url_2 = session_faker.uri()

    findings_3 = [session_faker.pydict(allowed_types=[str, int]) for _ in range(10)]

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

        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings",
            payload={"links": {"next": next_url_1}, "results": findings_1},
            repeat=True,
        )

        await connector.process_findings_for_company(queue, company_id)

        results = []
        while not queue.empty():
            results.append(await queue.get())

        # result should contain findings from all 3 pages and a None value
        assert results == [(finding, company_id) for finding in findings_1 + findings_2 + findings_3 + [None]]


@pytest.mark.asyncio
async def test_pull_findings_connector_consume_finding_events(connector: PullFindingsConnector, session_faker: Faker):
    """
    Test PullFindingsConnector.consume_finding_events with findings.

    Args:
        connector: PullFindingsConnector
        session_faker: Faker
    """
    connector.configuration.batch_limit = 2

    date_1 = (
        (datetime.now() - timedelta(days=3)).replace(microsecond=0, second=0, minute=0, hour=0).strftime("%Y-%m-%d")
    )

    findings_1 = [
        {
            **session_faker.pydict(allowed_types=[str, int]),
            "last_seen": date_1,
            "assets": [session_faker.word(), session_faker.word()],
        }
        for _ in range(5)
    ]
    company_id_1 = session_faker.word()

    date_2 = (
        (datetime.now() - timedelta(days=1)).replace(microsecond=0, second=0, minute=0, hour=0).strftime("%Y-%m-%d")
    )
    findings_2 = [
        {
            **session_faker.pydict(allowed_types=[str, int]),
            "last_seen": date_2,
            "assets": [session_faker.word(), session_faker.word()],
        }
        for _ in range(6)
    ]
    company_id_2 = session_faker.word()

    queue: FindingQueue = Queue()

    for finding in findings_1:
        await queue.put((finding, company_id_1))

    for finding in findings_2:
        await queue.put((finding, company_id_2))

    await queue.put((None, company_id_1))
    await queue.put((None, company_id_2))

    assert queue.qsize() == len(findings_1) + len(findings_2) + 2

    # Checkpoint contains only one company and already contains an offset
    checkpoint = Checkpoint(
        values=[
            CompanyCheckpoint(company_uuid=company_id_1, last_seen=date_1, offset=123),
        ]
    )

    total_pushed_events = await connector.consume_finding_events(queue, checkpoint, [company_id_1, company_id_2])

    # Each finding contains two assets, so the total pushed events should be 2 * (len(findings_1) + len(findings_2))
    assert total_pushed_events == (len(findings_1) + len(findings_2)) * 2

    updated_checkpoint = connector.get_checkpoint()
    assert (
        updated_checkpoint.dict()
        == Checkpoint(
            values=[
                CompanyCheckpoint(company_uuid=company_id_1, last_seen=date_1, offset=123 + 5),
                CompanyCheckpoint(company_uuid=company_id_2, last_seen=date_2, offset=6),
            ]
        ).dict()
    )


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

    def new_finding(last_seen: str) -> dict:
        return {
            **session_faker.pydict(allowed_types=[str, int]),
            "last_seen": last_seen,
            "assets": [session_faker.word(), session_faker.word()],
            "details": {
                "vulnerabilities": [session_faker.word(), session_faker.word(), session_faker.word()],
                **session_faker.pydict(allowed_types=[str, int]),
            },
        }

    now = datetime.utcnow()

    now_minus_7_days = (
        (now - timedelta(days=7)).replace(microsecond=0, second=0, minute=0, hour=0).strftime("%Y-%m-%d")
    )

    date_1 = (now - timedelta(days=1)).isoformat()
    findings_1 = [new_finding(date_1) for _ in range(3)]

    date_2 = (now - timedelta(minutes=5)).isoformat()
    findings_2 = [new_finding(date_2) for _ in range(4)]

    with aioresponses() as mocked_responses:
        # Mock requests to company #1
        company_id_1: str = session_faker.word()
        next_url_1 = session_faker.uri()

        mocked_responses.get(
            f"https://api.bitsighttech.com/ratings/v1/companies/{company_id_1}/findings?last_seen={now_minus_7_days}",
            payload={"links": {"next": next_url_1}, "results": findings_1},
            repeat=True,
        )
        mocked_responses.get(next_url_1, payload={"results": findings_2}, repeat=True)

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
                    CompanyCheckpoint(company_uuid=company_id_1, last_seen=date_2, offset=4),
                    CompanyCheckpoint(company_uuid=company_id_2, last_seen=date_2, offset=4),
                ]
            ).dict()
        )

        assert connector.get_checkpoint().dict() == finish_checkpoint.dict()
