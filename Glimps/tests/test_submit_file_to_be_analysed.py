import os
import pytest
from glimps.submit_file_to_be_analysed_action import (
    SubmitFile,
    WaitForFile,
)
from glimps.models import (
    SubmitArgument,
    SubmitResponse,
    AnalysisDetails,
    GLIMPSConfiguration,
    WaitForResultArgument,
)
from gdetect import GDetectError
from unittest.mock import patch

test_base_url = "https://gmalware.ggp.glimps.re"


@pytest.mark.skipif("{'GLIMPS_API_KEY', 'GLIMPS_API_URL'}.issubset(os.environ.keys()) == False")
def test_integration_submit_file_to_be_analysed(add_file_to_storage):
    symphony_storage, file, _ = add_file_to_storage
    action = SubmitFile(data_path=symphony_storage)
    action.module.configuration = GLIMPSConfiguration(
        api_key=os.environ["GLIMPS_API_KEY"], base_url=os.environ["GLIMPS_API_URL"]
    )

    arguments = SubmitArgument(file_name=file)
    response: SubmitResponse = action.run(arguments)

    assert response is not None
    assert response.get("status") is True
    assert response.get("uuid") != ""


def test_submit_file_to_be_analysed_succeed(add_file_to_storage, token):
    symphony_storage, file, _ = add_file_to_storage

    action = SubmitFile(data_path=symphony_storage)
    action.module.configuration = GLIMPSConfiguration(api_key=token, base_url=test_base_url)

    arguments = SubmitArgument(file_name=file)
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    with patch("gdetect.api.Client.push") as mock:
        mock.return_value = uuid
        response: SubmitResponse = action.run(arguments)

    assert response is not None
    assert response.get("status") is True
    assert response.get("uuid") == uuid


def test_submit_file_gdetect_error(add_file_to_storage, token):
    symphony_storage, file, _ = add_file_to_storage
    action = SubmitFile(data_path=symphony_storage)
    action.module.configuration = GLIMPSConfiguration(api_key=token, base_url=test_base_url)

    arguments = SubmitArgument(file_name=file)

    with patch("gdetect.api.Client.push") as mock:
        mock.side_effect = GDetectError("invalid GLIMPS Detect response")
        with pytest.raises(GDetectError):
            action.run(arguments)


def test_submit_file_error(add_file_to_storage, token):
    symphony_storage, file, _ = add_file_to_storage
    action = SubmitFile(data_path=symphony_storage)
    action.module.configuration = GLIMPSConfiguration(api_key=token, base_url=test_base_url)

    arguments = SubmitArgument(file_name=file)

    with patch("gdetect.api.Client.push") as mock:
        mock.side_effect = Exception("random exception")
        with pytest.raises(Exception):
            action.run(arguments)


@pytest.mark.skipif("'GLIMPS_API_KEY' not in os.environ.keys()")
def test_integration_wait_for_analysis(add_file_to_storage):
    symphony_storage, file, sha256 = add_file_to_storage
    action = WaitForFile(data_path=symphony_storage)
    action.module.configuration = GLIMPSConfiguration(api_key=os.environ["GLIMPS_API_KEY"], base_url=test_base_url)

    arguments = WaitForResultArgument(file_name=file)
    response: AnalysisDetails = action.run(arguments)

    assert response is not None
    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("sha256") == sha256


def test_wait_for_succeed(add_file_to_storage, set_up_wait_for_action, analysis_result):
    _, file, _ = add_file_to_storage
    action: WaitForFile = set_up_wait_for_action

    uuid, mock_analysis_result = analysis_result
    arguments = WaitForResultArgument(file_name=file)
    with patch("gdetect.api.Client.push_reader") as mock_push:
        mock_push.return_value = {"status": True, "uuid": uuid}
        with patch("gdetect.api.Client.get_by_uuid") as mock_pull:
            mock_pull.return_value = mock_analysis_result
            response: AnalysisDetails = action.run(arguments)

    assert response is not None
    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("uuid") == uuid
    assert response.get("view_url") == ""


def test_wait_for_view_token(add_file_to_storage, set_up_wait_for_action, analysis_result):
    _, file, _ = add_file_to_storage
    action: WaitForFile = set_up_wait_for_action

    uuid, mock_analysis_result = analysis_result
    mock_analysis_result.update({"token": "sometoken"})
    arguments = WaitForResultArgument(file_name=file)
    with patch("gdetect.api.Client.push_reader") as mock_push:
        mock_push.return_value = {"status": True, "uuid": uuid}
        with patch("gdetect.api.Client.get_by_uuid") as mock_pull:
            mock_pull.return_value = mock_analysis_result
            response: AnalysisDetails = action.run(arguments)

    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("uuid") == uuid
    assert response.get("analysis").get("error") is None
    assert response.get("view_url") is not None and response.get("view_url") != ""


def test_wait_for_timeout(add_file_to_storage, set_up_wait_for_action, analysis_result):
    _, file, _ = add_file_to_storage
    action: WaitForFile = set_up_wait_for_action
    uuid, mock_analysis_result = analysis_result
    # set very small timeout to trigger timeout exception
    arguments = WaitForResultArgument(file_name=file, timeout=0.1, pull_time=0.1)
    with patch("gdetect.api.Client.push_reader") as mock_push:
        mock_push.return_value = mock_analysis_result
        with patch("gdetect.api.Client.get_by_uuid") as mock_pull:
            mock_pull.return_value = {"status": True, "done": False}
            with pytest.raises(GDetectError):
                action.run(arguments)


def test_wait_for_exception(add_file_to_storage, set_up_wait_for_action):
    _, file, _ = add_file_to_storage
    action: WaitForFile = set_up_wait_for_action

    # set very small timeout to trigger timeout exception
    arguments = WaitForResultArgument(file_name=file, timeout=1, pull_time=1)
    with patch("gdetect.api.Client.waitfor") as mock:
        mock.side_effect = Exception("some error")
        with pytest.raises(Exception):
            action.run(arguments)
