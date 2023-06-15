from harfanglab.endpoint_actions import EndpointAgentIsolationAction


def test_base_get_url(symphony_storage):
    module_configuration = {
        "api_token": "token",
        "url": "http://harfang.url/",
    }
    action = EndpointAgentIsolationAction(data_path=symphony_storage)
    action.module.configuration = module_configuration
    url = action.get_url({"id": "foo"})
    assert url == "http://harfang.url/api/data/endpoint/Agent/foo/isolate/"
