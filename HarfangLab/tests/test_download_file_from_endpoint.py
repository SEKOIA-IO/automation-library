import os
from uuid import UUID
import requests_mock
from harfanglab.download_file_from_endpoint import (
    DownloadFileFromEndpointAction,
)


def test_download_file_from_endpoint(symphony_storage):
    # TODO: Make this test useful :)
    with requests_mock.Mocker() as m:
        m.post("http://mock.test/download/stuff", status_code=200, content=b"abcd")

        action = DownloadFileFromEndpointAction(data_path=symphony_storage)
        action.module.configuration = {
            "api_token": os.getenv("HARFANGLAB_API_TOKEN", "abcd"),
            "url": os.getenv("HARFANGLAB_URL", "http://mock.test"),
        }

        arguments = {
            "id": os.getenv("HARFANGLAB_AGENT_ID", "xxx"),
            "path": "C:\\tmp.txt",
        }

        response = action.run(arguments)

        assert UUID(response["path"].split("/")[-1])
        assert response["path"].startswith(str(symphony_storage))
        with open(response["path"], "rb") as f:
            assert f.read() == b"abcd"
