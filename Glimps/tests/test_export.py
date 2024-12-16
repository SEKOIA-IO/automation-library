import pytest
from glimps.models import (
    GLIMPSConfiguration,
    ExportSubmissionArguments,
)
from glimps.export_action import ExportSubmission
from unittest.mock import patch
from gdetect import GDetectError
from pydantic.error_wrappers import ValidationError
import os
from glimps.submit_file_to_be_analysed_action import (
    WaitForFile,
    WaitForResultArgument,
    AnalysisResponse,
)

test_base_url = "https://gmalware.ggp.glimps.re"


# NB: GGP lite version doesn't yet allow to export result analysis
@pytest.mark.skipif("{'GLIMPS_API_KEY', 'GLIMPS_API_URL'}.issubset(os.environ.keys()) == False")
def test_integration_get_export(add_file_to_storage):
    symphony_storage, file, _ = add_file_to_storage
    module_configuration = GLIMPSConfiguration(
        api_key=os.environ["GLIMPS_API_KEY"],
        base_url=os.environ["GLIMPS_API_URL"],
    )

    prepare = WaitForFile(data_path=symphony_storage)
    prepare.module.configuration = module_configuration

    arguments = WaitForResultArgument(file_name=file)
    response: AnalysisResponse = prepare.run(arguments)
    assert response is not None
    assert response.get("analysis").get("status") is True
    assert response.get("analysis").get("uuid") != ""

    action = ExportSubmission()
    action.module.configuration = module_configuration
    args = ExportSubmissionArguments(uuid=response.get("analysis").get("uuid"), format="csv", layout="en")

    response: bytes = action.run(args)
    assert response is not None
    assert response.decode("utf-8") != ""


def test_export_succeed(module):
    action = ExportSubmission(module=module)
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    arguments = ExportSubmissionArguments(uuid=uuid, layout="fr", format="csv")

    with patch("gdetect.api.Client.export_result") as mock:
        mock.return_value = b"key1,key2\nval1,val2"
        response: bytes = action.run(arguments)

    assert response is not None
    assert response.decode("utf-8") != ""


def test_export_error(module):
    action = ExportSubmission(module=module)
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    arguments = ExportSubmissionArguments(uuid=uuid, layout="fr", format="csv")

    with patch("gdetect.api.Client.export_result") as mock:
        mock.side_effect = GDetectError("some error")
        with pytest.raises(GDetectError):
            action.run(arguments)


def test_export_bad_format():
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    with pytest.raises(ValidationError):
        ExportSubmissionArguments(uuid=uuid, format="bad_format", layout="fr")


def test_export_bad_layout():
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    with pytest.raises(ValidationError):
        ExportSubmissionArguments(uuid=uuid, format="csv", layout="bad_layout")
