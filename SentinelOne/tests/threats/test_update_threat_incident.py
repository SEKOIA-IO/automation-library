import pytest
import requests_mock

from sentinelone_module.threats.update_threat_incident import (
    UpdateThreatIncidentAction,
    UpdateThreatIncidentArguments,
)


@pytest.fixture(scope="module")
def arguments():
    return UpdateThreatIncidentArguments(status="resolved", filters=None)


def test_update_threat_incident(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    update_action = UpdateThreatIncidentAction(module=sentinelone_module, data_path=symphony_storage)
    
    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/threats/incident",
            json={"data": {"affected": 1}},
        )
        
        results = update_action.run(arguments)

        assert results["affected"] > 0
