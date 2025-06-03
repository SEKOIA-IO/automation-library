# coding: utf-8

# natives

# third parties
from unittest.mock import MagicMock

import requests_mock

# internals
from harfanglab.get_process_list_action import GetProcessListAction
from harfanglab.models import JobAction, JobTarget, JobTriggerResult


def test_with_one_target_group():
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = GetProcessListAction()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    with requests_mock.Mocker() as mock:
        # Example from api doc
        mocked_response = {
            "agent_count": "<integer>",
            "creator": {"username": "GV", "id": "<integer>"},
            "jobs": ["persistanceScanner", "getPipeList"],
            "archived": "<boolean>",
            "creationtime": "2021-04-11T11:06:40.089232Z",
            "description": "<string>",
            "id": "ff3acfea-e3fb-496c-919f-d3a6afb28a24",
            "source_id": "<string>",
            "source_type": "agent",
            "template": "<string>",
            "title": "<string>",
        }
        mock.post(
            f"{instance_url}/api/data/job/batch/",
            json=mocked_response,
        )
        res = action.run(
            {
                "target_agents": "",
                "target_groups": "default_policy_group_id",
                "get_connections_list": False,
                "get_handles_list": False,
                "get_signatures_list": False,
            }
        )

        assert res == {
            "id": "ff3acfea-e3fb-496c-919f-d3a6afb28a24",
            "action": "getProcessList",
            "creationtime": "2021-04-11T11:06:40.089232Z",
            "parameters": {
                "getHandlesList": False,
                "getConnectionsList": False,
                "getSignaturesInfo": False,
            },
        }


def test_with_two_target_groups():
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = GetProcessListAction()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    trigger_job_mock = MagicMock(
        return_value=JobTriggerResult(
            id="595ad86a-c98a-4fc6-8b6d-8a7723e6d386",
            action="getProcessList",
            creationtime="2021-04-11T12:27:23.179844Z",
            parameters={
                "getHandlesList": False,
                "getConnectionsList": False,
                "getSignaturesInfo": False,
            },
        )
    )

    action.trigger_job = trigger_job_mock
    action.run(
        {
            "target_agents": "",
            "target_groups": "default_policy_group_id,mIXTwHgB9x_xfY4PJueN",
            "get_connections_list": False,
            "get_handles_list": False,
            "get_signatures_list": False,
        }
    )

    call_kwargs = trigger_job_mock.call_args.kwargs
    assert call_kwargs["target"] == JobTarget(group_ids=["default_policy_group_id", "mIXTwHgB9x_xfY4PJueN"])
    assert call_kwargs["job"] == JobAction(
        value="getProcessList",
        params={
            "getHandlesList": False,
            "getConnectionsList": False,
            "getSignaturesInfo": False,
        },
    )


def test_with_one_target_agent():
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = GetProcessListAction()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    trigger_job_mock = MagicMock(
        return_value=JobTriggerResult(
            id="595ad86a-c98a-4fc6-8b6d-8a7723e6d386",
            action="getProcessList",
            creationtime="2021-04-11T12:27:23.179844Z",
            parameters={
                "getHandlesList": False,
                "getConnectionsList": False,
                "getSignaturesInfo": False,
            },
        )
    )

    action.trigger_job = trigger_job_mock
    action.run(
        {
            "target_agents": "my-agent1",
            "target_groups": "",
            "get_connections_list": True,
            "get_handles_list": False,
            "get_signatures_list": False,
        }
    )
    call_kwargs = trigger_job_mock.call_args.kwargs
    assert call_kwargs["target"] == JobTarget(agent_ids=["my-agent1"])
    assert call_kwargs["job"] == JobAction(
        value="getProcessList",
        params={
            "getHandlesList": False,
            "getConnectionsList": True,
            "getSignaturesInfo": False,
        },
    )
