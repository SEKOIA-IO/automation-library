import os
import pytest
from unittest.mock import patch

from glimps.retrieve_analysis_action import RetrieveAnalysis
from glimps.submit_file_to_be_analysed_action import SubmitFile
from glimps.models import (
    SubmitArgument,
    SubmitResponse,
    AnalysisResponse,
    GLIMPSConfiguration,
    GetAnalysisByUUIDArgument,
)
from gdetect import BadUUIDError


@pytest.mark.skipif("{'GLIMPS_API_KEY', 'GLIMPS_API_URL'}.issubset(os.environ.keys()) == False")
def test_integration_retrieve_analysis(add_file_to_storage):
    symphony_storage, file, _ = add_file_to_storage
    module_configuration = GLIMPSConfiguration(
        api_key=os.environ["GLIMPS_API_KEY"],
        base_url=os.environ["GLIMPS_API_URL"],
    )
    prepare = SubmitFile(data_path=symphony_storage)
    prepare.module.configuration = module_configuration

    arguments = SubmitArgument(file_name=file)
    response: SubmitResponse = prepare.run(arguments)
    assert response is not None
    assert response.get("status") is True
    assert response.get("uuid") != ""

    action = RetrieveAnalysis(data_path=symphony_storage)
    action.module.configuration = module_configuration

    arguments = GetAnalysisByUUIDArgument(uuid=response.get("uuid"))

    response = action.run(arguments)
    assert response is not None
    assert response.get("analysis").get("status") is True


def test_retrieve_analysis(module, analysis_result):
    action = RetrieveAnalysis(module=module)
    uuid, mock_analysis_result = analysis_result
    arguments = GetAnalysisByUUIDArgument(uuid=uuid)
    with patch("gdetect.api.Client.get_by_uuid") as mock:
        mock.return_value = mock_analysis_result
        response: AnalysisResponse = action.run(arguments)

    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("uuid") == uuid
    assert response.get("analysis").get("error") is None


def test_retrieve_analysis_view_token(module, analysis_result):
    action = RetrieveAnalysis(module=module)
    uuid, mock_analysis_result = analysis_result
    mock_analysis_result.update({"token": "sometoken"})
    arguments = GetAnalysisByUUIDArgument(uuid=uuid)
    with patch("gdetect.api.Client.get_by_uuid") as mock:
        mock.return_value = mock_analysis_result
        response: AnalysisResponse = action.run(arguments)

    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("uuid") == uuid
    assert response.get("analysis").get("error") is None
    assert response.get("view_url") is not None and response.get("view_url") != ""


def test_retrieve_analysis_error(module):
    action = RetrieveAnalysis(module=module)
    arguments = GetAnalysisByUUIDArgument(uuid="c5ff79ed-b2d2-4b1b-b93c-7197bdaa8445")
    with patch("gdetect.api.Client.get_by_uuid") as mock:
        mock.side_effect = Exception("random exception")
        with pytest.raises(Exception):
            action.run(arguments)


def test_retrieve_analysis_gdetect_error(module):
    action = RetrieveAnalysis(module=module)
    arguments = GetAnalysisByUUIDArgument(uuid="bad-uuid")
    with patch("gdetect.api.Client.get_by_uuid") as mock:
        mock.side_effect = BadUUIDError
        with pytest.raises(BadUUIDError):
            action.run(arguments)
