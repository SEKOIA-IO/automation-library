import os
import shutil

import pytest
import requests_mock

from glimps import RetrieveAnalysis, SubmitFileToBeAnalysed


@pytest.mark.skipif("'GLIMPS_API_KEY' not in os.environ.keys()")
def test_integration_retrieve_analysis(symphony_storage):
    module_configuration = {
        "api_key": os.environ["GLIMPS_API_KEY"],
        "base_url": "https://gmalware.ggp.glimps.re",
    }
    prepare = SubmitFileToBeAnalysed(data_path=symphony_storage)
    prepare.module.configuration = module_configuration

    file_name = "eicar.txt"
    file_path = symphony_storage / file_name
    shutil.copyfileobj(open("tests/eicar.txt"), file_path.open("w+"))

    arguments = {"file": file_name}

    response = prepare.run(arguments)

    assert response is not None
    assert response.get("status", False) is True
    assert response.get("uuid")

    action = RetrieveAnalysis(data_path=symphony_storage)
    action.module.configuration = module_configuration

    arguments = {"uuid": response.get("uuid")}

    response = action.run(arguments)
    assert response is not None
    assert response.get("status", False) is True


def test_retrieve_analysis():
    action = RetrieveAnalysis()
    action.module.configuration = {
        "api_key": "api_key",
        "base_url": "https://gmalware.ggp.glimps.re",
    }

    arguments = {"uuid": "c5ff79ed-b2d2-4b1b-b93c-7197bdaa8445"}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://gmalware.ggp.glimps.re/api/lite/v2/results/c5ff79ed-b2d2-4b1b-b93c-7197bdaa8445",
            status_code=200,
            json={"uuid": "c5ff79ed-b2d2-4b1b-b93c-7197bdaa8445", "status": True},
        )
        response = action.run(arguments)

    assert response is not None
    assert response.get("status", False) is True
    assert response.get("uuid") == "c5ff79ed-b2d2-4b1b-b93c-7197bdaa8445"
