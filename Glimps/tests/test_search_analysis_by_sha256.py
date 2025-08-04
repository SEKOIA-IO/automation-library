import os
import pytest
from unittest.mock import patch

from glimps.search_analysis_by_sha256_action import SearchPreviousAnalysis
from glimps.submit_file_to_be_analysed_action import SubmitFile
from glimps.models import (
    SubmitArgument,
    SubmitResponse,
    AnalysisResponse,
    GLIMPSConfiguration,
    SearchAnalysisBySha256Argument,
)
from gdetect import BadSHA256Error


@pytest.mark.skipif("{'GLIMPS_API_KEY', 'GLIMPS_API_URL'}.issubset(os.environ.keys()) == False")
def test_integration_search_analysis(add_file_to_storage):
    symphony_storage, file, sha256 = add_file_to_storage
    module_configuration = GLIMPSConfiguration(
        api_key=os.environ["GLIMPS_API_KEY"], base_url=os.environ["GLIMPS_API_URL"]
    )
    prepare = SubmitFile(data_path=symphony_storage)
    prepare.module.configuration = module_configuration

    arguments = SubmitArgument(file_name=file)
    submit_response: SubmitResponse = prepare.run(arguments)

    assert submit_response is not None
    assert submit_response.get("status") is True
    assert submit_response.get("uuid") != ""

    action = SearchPreviousAnalysis(data_path=symphony_storage)
    action.module.configuration = module_configuration

    arguments = SearchAnalysisBySha256Argument(sha256=sha256)

    response: AnalysisResponse = action.run(arguments)
    assert response is not None
    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("uuid") == submit_response.get("uuid")


def test_search_analysis(module, analysis_result):
    action = SearchPreviousAnalysis(module=module)
    arguments = SearchAnalysisBySha256Argument(
        sha256="131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267"
    )
    uuid, mock_analysis_result = analysis_result
    with patch("gdetect.api.Client.get_by_sha256") as mock:
        mock.return_value = mock_analysis_result
        response: AnalysisResponse = action.run(arguments)

    assert response is not None
    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("uuid") == uuid


def test_search_analysis_view_token(module, analysis_result):
    action = SearchPreviousAnalysis(module=module)
    arguments = SearchAnalysisBySha256Argument(
        sha256="131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267"
    )
    uuid, mock_analysis_result = analysis_result
    mock_analysis_result.update({"token": "sometoken"})
    with patch("gdetect.api.Client.get_by_sha256") as mock:
        mock.return_value = mock_analysis_result
        response: AnalysisResponse = action.run(arguments)

    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("uuid") == uuid
    assert response.get("view_url") is not None and response.get("view_url") != ""


def test_search_analysis_error(module):
    action = SearchPreviousAnalysis(module=module)
    arguments = SearchAnalysisBySha256Argument(
        sha256="131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267"
    )
    with patch("gdetect.api.Client.get_by_sha256") as mock:
        mock.side_effect = Exception("random exception")
        with pytest.raises(Exception):
            action.run(arguments)


def test_retrieve_analysis_gdetect_error(module):
    action = SearchPreviousAnalysis(module=module)
    arguments = SearchAnalysisBySha256Argument(sha256="bad-sha256")
    with patch("gdetect.api.Client.get_by_uuid") as mock:
        mock.side_effect = BadSHA256Error
        with pytest.raises(BadSHA256Error):
            action.run(arguments)
