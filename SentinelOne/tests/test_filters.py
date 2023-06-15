from management.common.query_filter import QueryFilter
from management.mgmtsdk_v2.services.agent_actions import AgentsDangerousActionFilter

from sentinelone_module.filters import BaseFilters


class TestArguments(BaseFilters):
    __test__ = False

    account_ids: list[str] | None
    group_ids: list[str] | None
    ids: list[str] | None
    site_ids: list[str] | None
    query: str | None

    class Config:
        query_filter_class = AgentsDangerousActionFilter


def test_to_filters():
    arguments = TestArguments(
        account_ids=["account1", "account2"],
        group_ids=["group1", "group2"],
        site_ids=["site1", "site2"],
        ids=["id1", "id2"],
        query="query",
    )

    query_filter = arguments.to_query_filter()

    assert isinstance(query_filter, QueryFilter)
    assert query_filter.filters == {
        "accountIds": ["account1", "account2"],
        "groupIds": ["group1", "group2"],
        "siteIds": ["site1", "site2"],
        "ids": ["id1", "id2"],
        "query": "query",
    }
