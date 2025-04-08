import requests_mock

from trendmicro_modules.action_vision_one_add_alert_note import AddAlertNoteAction
from trendmicro_modules.action_vision_one_collect_file import CollectFileAction
from trendmicro_modules.action_vision_one_deisolate_machine import DeIsolateMachineAction
from trendmicro_modules.action_vision_one_isolate_machine import IsolateMachineAction
from trendmicro_modules.action_vision_one_scan_machine import ScanMachineAction
from trendmicro_modules.action_vision_one_terminate_process import TerminateProcessAction
from trendmicro_modules.action_vision_one_update_alert import UpdateAlertAction


def test_add_alert_note():
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/workbench/alerts/WB-00000-20241217-00001/notes",
            content=b"",
            status_code=201,
        )

        action = AddAlertNoteAction()
        action.run(
            arguments={
                "base_url": "https://api.eu.xdr.trendmicro.com",
                "api_key": "API_KEY_HERE",
                "alert_id": "WB-00000-20241217-00001",
                "note": "Some note",
            }
        )


def test_collect_file_action():
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

        action = CollectFileAction()
        action.run(
            arguments={
                "base_url": "https://api.eu.xdr.trendmicro.com",
                "api_key": "API_KEY_HERE",
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "file_path": "/etc/hosts",
                "description": "Some Description",
            }
        )


def test_deisolate_machine_action():
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

        action = DeIsolateMachineAction()
        action.run(
            arguments={
                "base_url": "https://api.eu.xdr.trendmicro.com",
                "api_key": "API_KEY_HERE",
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "description": "Some Description",
            }
        )


def test_isolate_machine_action():
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

        action = IsolateMachineAction()
        action.run(
            arguments={
                "base_url": "https://api.eu.xdr.trendmicro.com",
                "api_key": "API_KEY_HERE",
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "description": "Some Description",
            }
        )


def test_scan_machine_action():
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/response/endpoints/startMalwareScan",
            status_code=202,
            content=b"",
            headers={"Operation-Location": "https://api.eu.xdr.trendmicro.com/v3.0/xdr/response/tasks/00000001"},
        )

        action = ScanMachineAction()
        action.run(
            arguments={
                "base_url": "https://api.eu.xdr.trendmicro.com",
                "api_key": "API_KEY_HERE",
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "description": "Some Description",
            }
        )


def test_terminate_process_action():
    with requests_mock.Mocker() as mock:
        mock.post(
            url="https://api.eu.xdr.trendmicro.com/v3.0/response/endpoints/terminateProcess",
            status_code=202,
            content=b"",
            headers={"Operation-Location": "https://api.eu.xdr.trendmicro.com/v3.0/xdr/response/tasks/00000001"},
        )

        action = TerminateProcessAction()
        action.run(
            arguments={
                "base_url": "https://api.eu.xdr.trendmicro.com",
                "api_key": "API_KEY_HERE",
                "agent_guids": ["171d5516-f91b-41d6-82c0-3096fd6df927"],
                "description": "Some Description",
                "file_sha1": "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed",
            }
        )


def test_update_alert_action():
    with requests_mock.Mocker() as mock:
        mock.patch(
            url="https://api.eu.xdr.trendmicro.com/v3.0/workbench/alerts/WB-00000-20241217-00001",
            status_code=204,
            content=b"",
        )

        action = UpdateAlertAction()
        action.run(
            arguments={
                "base_url": "https://api.eu.xdr.trendmicro.com",
                "api_key": "API_KEY_HERE",
                "alert_id": "WB-00000-20241217-00001",
                "status": "In Progress",
                "investigation_result": "Noteworthy",
            }
        )
