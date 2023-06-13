import os
import shutil

import pytest
import requests_mock

from glimps import SubmitFileToBeAnalysed
from glimps.errors import MaxFileSizeExceedError


@pytest.mark.skipif("'GLIMPS_API_KEY' not in os.environ.keys()")
def test_submit_file_to_be_analysed(symphony_storage):
    action = SubmitFileToBeAnalysed(data_path=symphony_storage)
    action.module.configuration = {
        "api_key": os.environ["GLIMPS_API_KEY"],
        "base_url": "https://gmalware.ggp.glimps.re",
    }

    file_name = "eicar.txt"
    file_path = symphony_storage / file_name
    shutil.copyfileobj(open("tests/eicar.txt"), file_path.open("w+"))

    arguments = {"file": file_name}

    response = action.run(arguments)

    assert response is not None
    assert response.get("status", False) is True


def test_submit_file_to_be_analysed_succeed(symphony_storage):
    action = SubmitFileToBeAnalysed(data_path=symphony_storage)
    action.module.configuration = {
        "api_key": "api_key",
        "base_url": "https://gmalware.ggp.glimps.re",
    }

    file_name = "eicar1.txt"
    file_path = symphony_storage / file_name
    with file_path.open("w+") as f:
        f.write("a" * 40000000)

    arguments = {"file": file_name}

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://gmalware.ggp.glimps.re/api/lite/v2/submit",
            status_code=200,
            json={"uuid": "1da0cb84-c5cc-4832-8882-4a7e9df11ed2", "status": True},
        )
        response = action.run(arguments)

    assert response is not None
    assert response.get("status", False) is True
    assert response.get("uuid") == "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"


def test_submit_file_to_be_analysed_filesize_exceed(symphony_storage):
    action = SubmitFileToBeAnalysed(data_path=symphony_storage)
    action.module.configuration = {
        "api_key": "api_key",
        "base_url": "https://gmalware.ggp.glimps.re",
    }

    file_name = "eicar2.txt"
    file_path = symphony_storage / file_name
    with file_path.open("w+") as f:
        f.write("b" * 40000001)

    arguments = {"file": file_name}

    with pytest.raises(MaxFileSizeExceedError):
        action.run(arguments)
