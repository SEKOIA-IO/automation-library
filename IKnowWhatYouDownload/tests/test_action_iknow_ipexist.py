import requests_mock

from iknowwhatyoudownload.action_iknow_ipexist import IKnowIPExistAction


def test_query_ip():
    action = IKnowIPExistAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        ip = "185.122.161.248"

        send_result = {"ip": ip, "exists": False}
        mock.get(f"{host}/history/exist?key={key}&ip={ip}", json=send_result)

        results = action.run({"ip": ip})
        assert results == send_result

        assert mock.call_count == 1
        query = mock.request_history[0]
        assert query.method == "GET"
