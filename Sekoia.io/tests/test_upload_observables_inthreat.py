import json

import pytest
import requests_mock

from sekoiaio.intelligence_center.base import InThreatBaseAction
from sekoiaio.intelligence_center.upload_observables_inthreat import UploadObservablesAction

OBSERVABLES = [
    {"type": "ipv4-addr", "value": "1.2.3.4"},
    {"type": "domain-name", "value": "example.com"},
]


def make_action(symphony_storage) -> UploadObservablesAction:
    action = UploadObservablesAction(data_path=symphony_storage)
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}
    return action


def test_upload_observables(symphony_storage):
    action = make_action(symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/observables/bulk", json={})
        action.run({"observables": OBSERVABLES})

        assert mock.call_count == 1
        assert mock.last_request.json() == {"data": OBSERVABLES}
        assert mock.last_request.headers["Authorization"] == "Bearer fake_api_key"

    assert action._error is None


def test_upload_observables_from_file(symphony_storage):
    action = make_action(symphony_storage)
    (symphony_storage / "observables.json").write_text(json.dumps(OBSERVABLES))

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/observables/bulk", json={})
        action.run({"observables_path": "observables.json"})

        assert mock.last_request.json() == {"data": OBSERVABLES}

    assert action._error is None


def test_upload_observables_error(symphony_storage):
    action = make_action(symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/observables/bulk", status_code=400, text="invalid observables")
        action.run({"observables": OBSERVABLES})

    assert action._error == "Could not post observables: 'invalid observables', status code: 400"


def test_inthreat_base_action_run_is_not_implemented():
    with pytest.raises(NotImplementedError):
        InThreatBaseAction().run({})
