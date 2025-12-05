import pytest

@pytest.mark.asyncio
async def test_rule_filter_single(trigger):
    alert = {"rule": {"name": "A", "uuid": "u1"}}

    trigger.configuration.rule_filter = "A"
    assert trigger._matches_rule_filter(alert)

    trigger.configuration.rule_filter = "u1"
    assert trigger._matches_rule_filter(alert)

    trigger.configuration.rule_filter = "B"
    assert not trigger._matches_rule_filter(alert)


@pytest.mark.asyncio
async def test_rule_filter_multiple_names(trigger):
    alert = {"rule": {"name": "R1"}}

    trigger.configuration.rule_filter = None
    trigger.configuration.rule_names_filter = ["R1", "R2"]
    assert trigger._matches_rule_filter(alert)

    trigger.configuration.rule_names_filter = ["R2"]
    assert not trigger._matches_rule_filter(alert)
