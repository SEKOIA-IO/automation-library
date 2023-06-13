# coding: utf-8

# natives

# third parties
from unittest.mock import MagicMock

# internals
from harfanglab.get_pipe_list_action import GetPipeListAction
from harfanglab.models import JobTarget, JobTriggerResult


def test_trigger_job():
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = GetPipeListAction()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    trigger_job_mock = MagicMock(
        return_value=JobTriggerResult(
            id="595ad86a-c98a-4fc6-8b6d-8a7723e6d386",
            action="getPipeList",
            creationtime="2021-04-11T12:27:23.179844Z",
        )
    )

    action.trigger_job = trigger_job_mock
    action.run(
        {
            "target_agents": "",
            "target_groups": "default_policy_group_id",
        }
    )
    call_kwargs = trigger_job_mock.call_args.kwargs
    assert call_kwargs["target"] == JobTarget(agents=[], groups=["default_policy_group_id"])
    assert call_kwargs["actions"][0].label == "Pipelist"
    assert call_kwargs["actions"][0].value == "getPipeList"
