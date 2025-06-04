# coding: utf-8

# natives
from unittest.mock import MagicMock
import os

# third parties
import pytest

# internals
from harfanglab.get_pipe_list_action import GetPipeListAction
from harfanglab.models import JobAction, JobTarget, JobTriggerResult


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
    assert call_kwargs["target"] == JobTarget(group_ids=["default_policy_group_id"])
    assert call_kwargs["job"] == JobAction(value="getPipeList", params={})


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
