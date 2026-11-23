from typing import Any


async def collect(connector: Any) -> list[str]:
    """Run a collection cycle and return the events pushed to the intake during it."""
    push = connector.push_data_to_intakes
    already_pushed = len(push.call_args_list)

    forwarded = await connector.get_azure_blob_data()

    events = [event for call in push.call_args_list[already_pushed:] for event in call.kwargs["events"]]
    assert forwarded == len(events)
    return events
