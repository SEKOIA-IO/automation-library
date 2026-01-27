# coding: utf-8

import os
from typing import Any
from unittest.mock import patch

import pytest
import requests_mock

from harfanglab.get_pipe_list_action import GetPipeListAction


@pytest.fixture
def response_job_batched() -> dict[str, Any]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": None,
        "description": None,
        "creationtime": "2026-01-23T11:56:58.733422Z",
        "creator": {"id": 1, "username": "User"},
        "source_type": None,
        "source_id": None,
        "template": None,
        "archived": None,
        "agent_count": 1,
        "jobs": ["getProcessList"],
    }


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


def test_trigger_job(symphony_storage, response_job_batched, response_job_status_done):
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = GetPipeListAction(data_path=symphony_storage)
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    with requests_mock.Mocker() as requests_mocker, patch("harfanglab.get_pipe_list_action.sleep") as sleep_mock:
        requests_mocker.post(
            f"https://test.hurukau.io/api/data/job/batch/", status_code=201, json=response_job_batched
        )

        requests_mocker.get(
            f"https://test.hurukau.io/api/data/job/batch/11111111-1111-1111-1111-111111111111/",
            status_code=200,
            json=response_job_status_done,
        )

        requests_mocker.get(
            f"https://test.hurukau.io/api/data/investigation/hunting/Pipe/?job_id=11111111-1111-1111-1111-111111111111",
            status_code=200,
            json={},
        )

        action.run(
            {
                "target_agents": "",
                "target_groups": "default_policy_group_id",
            }
        )


@pytest.mark.skipif(
    """not all(map(os.environ.get, ("HARFANGLAB_URL", "HARFANGLAB_API_TOKEN", "HARFANGLAB_AGENT_ID")))""",
)
def test_integration_get_pipe_list_from_endpoint(symphony_storage) -> None:
    """Live test - Run only if some envvars are present."""

    action = GetPipeListAction(data_path=symphony_storage)
    action.module.configuration = {
        "url": os.environ["HARFANGLAB_URL"],
        "api_token": os.environ["HARFANGLAB_API_TOKEN"],
    }

    result = action.run({"target_agents": os.environ["HARFANGLAB_AGENT_ID"], "target_groups": ""})
    assert result is not None
    assert result.get("id") is not None
