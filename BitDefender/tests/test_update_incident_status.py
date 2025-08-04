import requests_mock
from bitdefender.actions.udpate_incident_status_action import UpdateIncidentStatusAction


def test_update_incident_status(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = UpdateIncidentStatusAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/incidents",
            json={"result": True},
            status_code=200,
        )
        arguments = {"type": "incidents", "incidentId": "12345", "status": "1"}
        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}


def test_update_incident_status_error(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = UpdateIncidentStatusAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/incidents",
            json={"error": "Invalid id provided."},
            status_code=400,
        )
        arguments = {"type": "incidents", "incidentId": "invalid_id", "status": "1"}

        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/incidents"
            )
