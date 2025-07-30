import requests_mock
from bitdefender.actions import DeisolateEndpointAction 

def test_create_isolate_endpoint(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = DeisolateEndpointAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/incidents/createRestoreEndpointFromIsolationTask",
            json={"result": True},
            status_code=200,
        )
        arguments = {"endpointId": "5b680f6fb1a43d860a7b23c1"}
        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}

def test_create_isolate_endpoint_error(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = DeisolateEndpointAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/incidents/createRestoreEndpointFromIsolationTask",
            json={"error": "Invalid endpoint ID"},
            status_code=400,
        )
        arguments = {"endpointId": "invalid_id"}
        
        try:
            action.run(arguments)
        except BaseException as e:
            assert str(e) == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/incidents/createRestoreEndpointFromIsolationTask"