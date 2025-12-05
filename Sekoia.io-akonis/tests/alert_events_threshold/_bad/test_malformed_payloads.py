import pytest
import json

@pytest.mark.asyncio
async def test_invalid_alert_api_response_not_dict(trigger, aresponses):

    aresponses.add(
        "mockserver",
        "/alert/a1",
        "get",
        aresponses.Response(
            status=200,
            text=json.dumps([1,2,3]),  # invalid: list instead of dict
            headers={"Content-Type": "application/json"}
        ),
    )

    with pytest.raises(ValueError):
        await trigger._retrieve_alert_from_alertapi("a1")


@pytest.mark.asyncio
async def test_invalid_alert_api_response_missing_uuid(trigger, aresponses):

    aresponses.add(
        "mockserver",
        "/alert/a1",
        "get",
        aresponses.Response(
            status=200,
            text=json.dumps({"foo": "bar"}),  # missing uuid
            headers={"Content-Type": "application/json"}
        ),
    )

    with pytest.raises(ValueError):
        await trigger._retrieve_alert_from_alertapi("a1")
