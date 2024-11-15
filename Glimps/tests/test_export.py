import pytest
from glimps.models import (
    GlimpsConfiguration,
    ExportSubmissionArguments,
)
from glimps.export_action import ExportSubmission
from unittest.mock import patch
from gdetect import GDetectError
from pydantic.error_wrappers import ValidationError

test_base_url = "https://gmalware.ggp.glimps.re"


# NB: GGP lite version doesn't yet allow to export result analysis
# @pytest.mark.skipif("'GLIMPS_API_KEY' not in os.environ.keys()")
# def test_integration_get_status(add_file_to_storage):
#     symphony_storage, file, _sha256 = add_file_to_storage
#     module_configuration = GlimpsConfiguration(
#         api_key=os.environ["GLIMPS_API_KEY"],
#         base_url=test_base_url,
#     )

#     prepare = SubmitFileToBeAnalysed(data_path=symphony_storage)
#     prepare.module.configuration = module_configuration

#     arguments = SubmitArgument(file_name=file)
#     response: SubmitResponse = prepare.run(arguments)
#     assert response is not None
#     assert response.get("status") is True
#     assert response.get("uuid") != ""

#     action = ExportSubmission()
#     action.module.configuration = module_configuration
#     args = ExportSubmissionArguments(
#         uuid=response.get("uuid"), format="csv", layout="en"
#     )

#     response: bytes = action.run(args)
#     assert response is not None
#     assert response.decode("utf-8") != ""


def test_export_succeed(token):
    action = ExportSubmission()
    action.module.configuration = GlimpsConfiguration(
        api_key=token, base_url=test_base_url
    )
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    arguments = ExportSubmissionArguments(uuid=uuid, layout="fr", format="csv")

    with patch("gdetect.api.Client.export_result") as mock:
        mock.return_value = b"key1,key2\nval1,val2"
        response: bytes = action.run(arguments)

    assert response is not None
    assert response.decode("utf-8") != ""


def test_export_error(token):
    action = ExportSubmission()
    action.module.configuration = GlimpsConfiguration(
        api_key=token, base_url=test_base_url
    )
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    arguments = ExportSubmissionArguments(uuid=uuid, layout="fr", format="csv")

    with patch("gdetect.api.Client.export_result") as mock:
        mock.side_effect = GDetectError("some error")
        with pytest.raises(GDetectError):
            action.run(arguments)


def test_export_bad_format(token):
    action = ExportSubmission()
    action.module.configuration = GlimpsConfiguration(
        api_key=token, base_url=test_base_url
    )
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    with pytest.raises(ValidationError):
        ExportSubmissionArguments(uuid=uuid, format="bad_format", layout="fr")


def test_export_bad_layout(token):
    action = ExportSubmission()
    action.module.configuration = GlimpsConfiguration(
        api_key=token, base_url=test_base_url
    )
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    with pytest.raises(ValidationError):
        ExportSubmissionArguments(uuid=uuid, format="csv", layout="bad_layout")
