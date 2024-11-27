import pytest
import requests_mock

from sentinelone_module.threats.create_threat_note import (
    CreateThreatNoteAction,
    CreateThreatNoteArguments,
    ThreatNoteFilters,
)


@pytest.fixture(scope="module")
def arguments():
    return CreateThreatNoteArguments(text="Threat note test", filters=ThreatNoteFilters(ids=["1234567890"]))


def test_create_threat_note(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    threat_note_action = CreateThreatNoteAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/threats/notes",
            json={"data": {"affected": 1}},
        )

        results = threat_note_action.run(arguments)

        assert results["affected"] > 0


def test_create_threat_note_no_filters(symphony_storage, sentinelone_hostname, sentinelone_module):
    threat_note_action = CreateThreatNoteAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )

        with pytest.raises(ValueError) as e:
            threat_note_action.run(CreateThreatNoteArguments(text="Threat note test", filters=None))
            assert str(e.value) == "Filters are required to create a threat note !!"
