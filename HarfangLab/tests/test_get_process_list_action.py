# coding: utf-8

# natives
import os
from typing import Any
from unittest.mock import MagicMock, patch

# third parties
import pytest
import requests_mock

# internals
from harfanglab.get_process_list_action import GetProcessListAction
from harfanglab.models import JobAction, JobTarget, JobTriggerResult


@pytest.fixture
def response_job_status_done() -> dict[str, Any]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": None,
        "description": None,
        "creationtime": "2026-01-26T10:40:06.844865Z",
        "creator": {"id": 1, "username": "Admin"},
        "source_type": None,
        "source_id": None,
        "template": None,
        "archived": False,
        "agent_count": 1,
        "tasks": [
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "task_id": 0,
                "action": {
                    "getProcessList": {
                        "auto_download_new_files": False,
                        "maxsize_files_download": 104857600,
                        "getConnectionsList": False,
                        "getHandlesList": False,
                        "getSignaturesInfo": False,
                    }
                },
                "status": {
                    "total": 1,
                    "done": 1,
                    "waiting": 0,
                    "running": 0,
                    "canceled": 0,
                    "injecting": 0,
                    "error": 0,
                },
                "can_read_action": True,
            }
        ],
        "status": {"total": 1, "done": 1, "waiting": 0, "running": 0, "canceled": 0, "injecting": 0, "error": 0},
    }


@pytest.fixture
def response_results() -> dict[str, Any]:
    return {"count": 0, "next": None, "previous": None, "results": []}


def test_with_one_target_group(symphony_storage, response_job_status_done):
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = GetProcessListAction(data_path=symphony_storage)
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    with requests_mock.Mocker() as requests_mocker, patch("harfanglab.get_process_list_action.sleep") as sleep_mock:
        # Example from api doc
        mocked_response = {
            "agent_count": "<integer>",
            "creator": {"username": "GV", "id": "<integer>"},
            "jobs": ["persistanceScanner", "getPipeList"],
            "archived": "<boolean>",
            "creationtime": "2021-04-11T11:06:40.089232Z",
            "description": "<string>",
            "id": "11111111-1111-1111-1111-111111111111",
            "source_id": "<string>",
            "source_type": "agent",
            "template": "<string>",
            "title": "<string>",
        }
        requests_mocker.post(
            f"{instance_url}/api/data/job/batch/",
            json=mocked_response,
        )

        requests_mocker.get(
            f"{instance_url}/api/data/job/batch/11111111-1111-1111-1111-111111111111/",
            status_code=200,
            json=response_job_status_done,
        )

        requests_mocker.get(
            f"{instance_url}/api/data/investigation/hunting/Process/?job_id=11111111-1111-1111-1111-111111111111",
            status_code=200,
            json={},
        )

        res = action.run(
            {
                "target_agents": "",
                "target_groups": "default_policy_group_id",
                "get_connections_list": False,
                "get_handles_list": False,
                "get_signatures_list": False,
                "save_to_file": False,
            }
        )

        assert res == {"results": []}


@pytest.mark.skipif(
    """not all(map(os.environ.get, ("HARFANGLAB_URL", "HARFANGLAB_API_TOKEN", "HARFANGLAB_AGENT_ID")))""",
)
def test_integration_get_process_from_endpoint(symphony_storage) -> None:
    """Live test - Run only if some envvars are present."""

    action = GetProcessListAction(data_path=symphony_storage)
    action.module.configuration = {
        "url": os.environ["HARFANGLAB_URL"],
        "api_token": os.environ["HARFANGLAB_API_TOKEN"],
    }

    result = action.run(
        {
            "target_agents": os.environ["HARFANGLAB_AGENT_ID"],
            "target_groups": "",
            "get_connections_list": True,
            "get_handles_list": False,
            "get_signatures_list": False,
        }
    )
    assert result is not None
    assert result.get("id") is not None
