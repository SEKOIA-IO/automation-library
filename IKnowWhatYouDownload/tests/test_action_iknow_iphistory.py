import requests_mock

from iknowwhatyoudownload.action_iknow_iphistory import IKnowIPHistoryAction


def test_query_ip():
    action = IKnowIPHistoryAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        ip = "185.122.161.248"

        send_result = {
            "ip": ip,
            "hasPorno": False,
            "hasChildPorno": False,
            "contents": [],
        }
        mock.get(f"{host}/history/peer/?key={key}&ip={ip}", json=send_result)

        results = action.run({"ip": ip})
        assert results == send_result

        assert mock.call_count == 1
        query = mock.request_history[0]
        assert query.method == "GET"
