import os
import pytest
from unittest.mock import patch

from glimps.retrieve_analysis_action import RetrieveAnalysis
from glimps.submit_file_to_be_analysed_action import SubmitFileToBeAnalysed
from glimps.models import (
    SubmitArgument,
    SubmitResponse,
    AnalysisResponse,
    GlimpsConfiguration,
    GetAnalysisByUUIDArgument,
)
from gdetect import BadUUIDError


@pytest.mark.skipif("'GLIMPS_API_KEY' not in os.environ.keys()")
def test_integration_retrieve_analysis(add_file_to_storage):
    symphony_storage, file, _ = add_file_to_storage
    module_configuration = GlimpsConfiguration(
        api_key=os.environ["GLIMPS_API_KEY"],
        base_url="https://gmalware.ggp.glimps.re",
    )
    prepare = SubmitFileToBeAnalysed(data_path=symphony_storage)
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
    assert response.get("status") is True


def test_retrieve_analysis(set_up_retrieve_analysis_action, analysis_result):
    action: RetrieveAnalysis = set_up_retrieve_analysis_action
    uuid, mock_analysis_result = analysis_result
    arguments = GetAnalysisByUUIDArgument(uuid=uuid)
    with patch("gdetect.api.Client.get_by_uuid") as mock:
        mock.return_value = mock_analysis_result
        response: AnalysisResponse = action.run(arguments)

    assert response.get("status") is True
    assert response.get("uuid") == uuid
    assert response.get("error") is None


def test_retrieve_analysis_error(set_up_retrieve_analysis_action):
    action: RetrieveAnalysis = set_up_retrieve_analysis_action
    arguments = GetAnalysisByUUIDArgument(uuid="c5ff79ed-b2d2-4b1b-b93c-7197bdaa8445")
    with patch("gdetect.api.Client.get_by_uuid") as mock:
        mock.side_effect = Exception("random exception")
        with pytest.raises(Exception):
            action.run(arguments)


def test_retrieve_analysis_gdetect_error(set_up_retrieve_analysis_action):
    action: RetrieveAnalysis = set_up_retrieve_analysis_action
    arguments = GetAnalysisByUUIDArgument(uuid="bad-uuid")
    with patch("gdetect.api.Client.get_by_uuid") as mock:
        mock.side_effect = BadUUIDError
        with pytest.raises(BadUUIDError):
            action.run(arguments)
