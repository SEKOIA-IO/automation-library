from bitdefender.base import BitdefenderAction 


def test_base_get_url(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "https://cloudgz.gravityzone.bitdefender.com",
    }
    action = BitdefenderAction(data_path=symphony_storage)
    action.endpoint_api = "api/v1.0/jsonrpc/incidents/createIsolateEndpointTask"
    action.method_name = "createIsolateEndpointTask"
    action.module.configuration = module_configuration
    url = action.get_api_url()
    assert url == "https://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/incidents/createIsolateEndpointTask"
