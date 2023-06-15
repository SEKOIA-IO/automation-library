from service_now import ServiceNowAction


def test_get_headers():
    action = ServiceNowAction()
    action.module._configuration = {"username": "foo", "password": "bar"}
    headers = action.get_headers()
    assert headers["Accept"] == "application/json"
    assert headers["Authorization"] == "Basic Zm9vOmJhcg=="
