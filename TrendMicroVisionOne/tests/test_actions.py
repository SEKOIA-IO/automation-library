import pytest
import requests_mock

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
                "agent_guids_process_ids": [{"agent_guid": "171d5516-f91b-41d6-82c0-3096fd6df927", "process_id": 123}],
                "description": "Some Description",
            }
        )


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
