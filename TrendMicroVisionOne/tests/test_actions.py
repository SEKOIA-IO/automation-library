import pytest
import requests_mock
from pydantic import ValidationError

from trendmicro_visionone_modules import TrendMicroVisionOneModule
from trendmicro_visionone_modules.action_vision_one_add_alert_note import AddAlertNoteAction
from trendmicro_visionone_modules.action_vision_one_collect_file import CollectFileAction
from trendmicro_visionone_modules.action_vision_one_deisolate_machine import DeIsolateMachineAction
from trendmicro_visionone_modules.action_vision_one_isolate_machine import IsolateMachineAction
from trendmicro_visionone_modules.action_vision_one_scan_machine import ScanMachineAction
from trendmicro_visionone_modules.action_vision_one_terminate_process import TerminateProcessAction
from trendmicro_visionone_modules.action_vision_one_update_alert import UpdateAlertAction


@pytest.fixture
def module():
    m = TrendMicroVisionOneModule()
    m.configuration = {
        "base_url": "https://api.eu.xdr.trendmicro.com",
        "api_key": "API_KEY_HERE",
    }

    return m


def test_add_alert_note(module):
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/workbench/alerts/WB-00000-20241217-00001/notes",
            content=b"",
            status_code=201,
        )

        action = AddAlertNoteAction(module)
        action.run(
            arguments={
                "alert_id": "WB-00000-20241217-00001",
                "note": "Some note",
            }
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"note": "Some note"},
        {"alert_id": "WB-00000-20241217-00001"},
        {"alert_id": "WB-00000-20241217-00001", "note": ""},
        {"alert_id": "   ", "note": "Some note"},
    ],
)
def test_add_alert_note_requires_entrypoint_arguments(module, arguments):
    with requests_mock.Mocker() as mock:
        action = AddAlertNoteAction(module)

        with pytest.raises(ValidationError):
            action.run(arguments=arguments)

        assert len(mock.request_history) == 0


def test_collect_file_action(module):
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/response/endpoints/collectFile",
            status_code=207,
            json=[
                {
                    "status": 202,
                    "headers": [
                        {
                            "name": "Operation-Location",
                            "value": "https://api.eu.xdr.trendmicro.com/v3.0/xdr/response/tasks/00000001",
                        }
                    ],
                }
            ],
        )

        action = CollectFileAction(module)
        action.run(
            arguments={
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "file_path": "/etc/hosts",
                "description": "Some Description",
            }
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"file_path": "/etc/hosts"},
        {"agent_guids": [], "file_path": "/etc/hosts"},
        {"agent_guids": ["not-a-uuid"], "file_path": "/etc/hosts"},
        {"agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"]},
        {"agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"], "file_path": ""},
        {"agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"], "file_path": "   "},
    ],
)
def test_collect_file_action_requires_entrypoint_arguments(module, arguments):
    with requests_mock.Mocker() as mock:
        action = CollectFileAction(module)

        with pytest.raises(ValidationError):
            action.run(arguments=arguments)

        assert len(mock.request_history) == 0


def test_deisolate_machine_action(module):
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/response/endpoints/restore",
            status_code=207,
            json=[
                {
                    "status": 202,
                    "headers": [
                        {
                            "name": "Operation-Location",
                            "value": "https://api.eu.xdr.trendmicro.com/v3.0/xdr/response/tasks/00000001",
                        }
                    ],
                }
            ],
        )

        action = DeIsolateMachineAction(module)
        action.run(
            arguments={
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "description": "Some Description",
            }
        )


@pytest.mark.parametrize("arguments", [{}, {"agent_guids": []}, {"agent_guids": ""}, {"agent_guids": ["not-a-uuid"]}])
def test_deisolate_machine_action_requires_agent_guids(module, arguments):
    with requests_mock.Mocker() as mock:
        action = DeIsolateMachineAction(module)

        with pytest.raises(ValidationError):
            action.run(arguments=arguments)

        assert len(mock.request_history) == 0


def test_isolate_machine_action(module):
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/response/endpoints/isolate",
            status_code=207,
            json=[
                {
                    "status": 202,
                    "headers": [
                        {
                            "name": "Operation-Location",
                            "value": "https://api.eu.xdr.trendmicro.com/v3.0/xdr/response/tasks/00000001",
                        }
                    ],
                }
            ],
        )

        action = IsolateMachineAction(module)
        action.run(
            arguments={
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "description": "Some Description",
            }
        )


@pytest.mark.parametrize("arguments", [{}, {"agent_guids": []}, {"agent_guids": ""}, {"agent_guids": ["not-a-uuid"]}])
def test_isolate_machine_action_requires_agent_guids(module, arguments):
    with requests_mock.Mocker() as mock:
        action = IsolateMachineAction(module)

        with pytest.raises(ValidationError):
            action.run(arguments=arguments)

        assert len(mock.request_history) == 0


def test_scan_machine_action(module):
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/response/endpoints/startMalwareScan",
            status_code=202,
            content=b"",
            headers={"Operation-Location": "https://api.eu.xdr.trendmicro.com/v3.0/xdr/response/tasks/00000001"},
        )

        action = ScanMachineAction(module)
        action.run(
            arguments={
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "description": "Some Description",
            }
        )


def test_terminate_process_action(module):
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/response/endpoints/terminateProcess",
            status_code=202,
            content=b"",
            headers={"Operation-Location": "https://api.eu.xdr.trendmicro.com/v3.0/xdr/response/tasks/00000001"},
        )

        action = TerminateProcessAction(module)
        action.run(
            arguments={
                "agent_guid": "171d5516-f91b-41d6-82c0-3096fd6df927",
                "process_id": 123,
                "file_name": "virus.exe",
                "description": "Some Description",
            }
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"process_id": 123, "file_name": "virus.exe"},
        {"agent_guid": "", "process_id": 123, "file_name": "virus.exe"},
        {"agent_guid": "not-a-uuid", "process_id": 123, "file_name": "virus.exe"},
        {"agent_guid": "171d5516-f91b-41d6-82c0-3096fd6df927", "file_name": "virus.exe"},
        {"agent_guid": "171d5516-f91b-41d6-82c0-3096fd6df927", "process_id": 0, "file_name": "virus.exe"},
    ],
)
def test_terminate_process_action_requires_entrypoint_arguments(module, arguments):
    with requests_mock.Mocker() as mock:
        action = TerminateProcessAction(module)

        with pytest.raises(ValidationError):
            action.run(arguments=arguments)

        assert len(mock.request_history) == 0


def test_update_alert_action(module):
    with requests_mock.Mocker() as mock:
        mock.patch(
            url="https://api.eu.xdr.trendmicro.com/v3.0/workbench/alerts/WB-00000-20241217-00001",
            status_code=204,
            content=b"",
        )

        action = UpdateAlertAction(module)
        action.run(
            arguments={
                "alert_id": "WB-00000-20241217-00001",
                "status": "In Progress",
                "investigation_result": "Noteworthy",
            }
        )


@pytest.mark.parametrize("arguments", [{}, {"alert_id": ""}, {"alert_id": "   "}])
def test_update_alert_action_requires_alert_id(module, arguments):
    with requests_mock.Mocker() as mock:
        action = UpdateAlertAction(module)

        with pytest.raises(ValidationError):
            action.run(arguments=arguments)

        assert len(mock.request_history) == 0
