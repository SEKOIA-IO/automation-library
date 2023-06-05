"""Tests to handle EDR response data."""
import orjson
import pytest

from client.schemas.attributes.events import ConfigurationAttributes
from client.schemas.attributes.investigations import InvestigationAttributes
from client.schemas.attributes.searches import SearchHistoricalAttributes, SearchRealtimeAttributes
from client.schemas.edr import TrellixEdrResponse


@pytest.mark.asyncio
async def test_edr_events_configuration(session_faker):
    """
    Test edr events configuration.

    Args:
        session_faker:
    """
    expected_response = {
        "type": session_faker.word(),
        "id": session_faker.word(),
        "attributes": {
            "emailIds": [
                session_faker.email(),
                session_faker.email(),
            ],
            "config": [
                {
                    "privacy": {
                        "maskedAttributes": [
                            session_faker.word(),
                            session_faker.word(),
                            session_faker.word(),
                        ]
                    },
                    "integrationType": session_faker.word(),
                    "awsKeyId": session_faker.word(),
                    "awsSecretKey": session_faker.word(),
                    "region": session_faker.word(),
                    "bucket": session_faker.word(),
                    "encryptionKey": session_faker.word(),
                    "datasource": session_faker.word(),
                    "filter": session_faker.word(),
                    "subFolder": session_faker.word(),
                    "authType": session_faker.word(),
                    "encryptionType": session_faker.word(),
                    "id": session_faker.word(),
                }
            ],
        },
    }

    response = TrellixEdrResponse[ConfigurationAttributes](**expected_response)

    assert isinstance(response, TrellixEdrResponse)
    assert isinstance(response.attributes, ConfigurationAttributes)
    assert response.dict() == expected_response


@pytest.mark.asyncio
async def test_edr_investigations(session_faker):
    """
    Test edr investigations.

    Args:
        session_faker:
    """
    expected_response = {
        "type": session_faker.word(),
        "id": session_faker.word(),
        "attributes": {
            "tenantId": session_faker.word(),
            "name": session_faker.word(),
            "summary": session_faker.word(),
            "owner": session_faker.word(),
            "created": session_faker.date_time(),
            "lastModified": session_faker.date_time(),
            "source": session_faker.word(),
            "isAutomatic": session_faker.boolean(),
            "investigated": session_faker.boolean(),
            "hint": session_faker.word(),
            "caseType": session_faker.word(),
            "status": session_faker.word(),
            "priority": session_faker.word(),
        },
    }

    response = TrellixEdrResponse[InvestigationAttributes](
        **orjson.loads(orjson.dumps(expected_response).decode("utf-8"))
    )

    assert isinstance(response, TrellixEdrResponse)
    assert isinstance(response.attributes, InvestigationAttributes)
    assert response.dict() == expected_response


@pytest.mark.asyncio
async def test_edr_searches_historical(session_faker):
    """
    Test edr searches historical.

    Args:
        session_faker:
    """
    expected_response = {
        "type": session_faker.word(),
        "id": session_faker.word(),
        "attributes": {
            "RuleId": session_faker.word(),
            "Maguid": session_faker.word(),
            "Logon_LogonType": session_faker.word(),
            "User_Domain": session_faker.word(),
            "Artifact": session_faker.word(),
            "Tags": [session_faker.word(), session_faker.word()],
            "Activity": session_faker.word(),
            "DeviceName": session_faker.word(),
            "DetectionDate": session_faker.date_time(),
            "Time": session_faker.date_time(),
        },
    }

    response = TrellixEdrResponse[SearchHistoricalAttributes](
        **orjson.loads(orjson.dumps(expected_response).decode("utf-8"))
    )

    assert isinstance(response, TrellixEdrResponse)
    assert isinstance(response.attributes, SearchHistoricalAttributes)
    assert response.dict() == expected_response


@pytest.mark.asyncio
async def test_edr_searches_realtime(session_faker):
    """
    Test edr searches realtime.

    Args:
        session_faker:
    """
    expected_response = {
        "type": session_faker.word(),
        "id": session_faker.word(),
        "attributes": {
            "created": session_faker.date_time(),
            "HostInfo.hostname": session_faker.word(),
            "HostInfo.ip_address": session_faker.ipv4(),
            "HostInfo.os": session_faker.word(),
            "HostInfo.connection_status": session_faker.word(),
            "HostInfo.platform": session_faker.word(),
            "BrowserHistory.url": session_faker.uri(),
            "BrowserHistory.title": session_faker.sentence(nb_words=3),
            "BrowserHistory.last_visit_time": session_faker.date_time(),
            "BrowserHistory.visit_count": session_faker.random_int(),
            "BrowserHistory.visit_from": session_faker.pyint(),
            "BrowserHistory.browser": session_faker.sentence(nb_words=3),
            "BrowserHistory.user_profile": session_faker.word(),
            "BrowserHistory.browser_profile": session_faker.word(),
            "BrowserHistory.url_length": session_faker.pyint(),
            "BrowserHistory.hidden": session_faker.pyint(),
            "BrowserHistory.typed_count": session_faker.pyint(),
        },
    }

    response = TrellixEdrResponse[SearchRealtimeAttributes](
        **orjson.loads(orjson.dumps(expected_response).decode("utf-8"))
    )

    assert isinstance(response, TrellixEdrResponse)
    assert isinstance(response.attributes, SearchRealtimeAttributes)
    # assert response.dict() == expected_response
