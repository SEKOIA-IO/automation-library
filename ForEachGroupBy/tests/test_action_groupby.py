import pytest
from groupby.action_groupby import GroupProcessor


class TestGroupProcessor:
    @pytest.fixture
    def processor(self):
        return GroupProcessor()

    def test_group_elements_no_filter(self, processor):
        arguments = {
            "key": "category",
            "input": [
                {"category": "A", "data": 1},
                {"category": "A", "data": 2},
                {"category": "B", "data": 3},
                {"category": "B", "data": 4},
                {"category": "C", "data": 5},
            ],
        }

        results = list(processor.run(arguments))

        # Check we have the expected number of groups
        assert len(results) == 3  # A, B, C

        # Validate the contents of each group
        assert results[0]["group_index"] == 0
        assert results[0]["total_groups"] == 3
        assert results[0]["group_data"] == [{"category": "A", "data": 1}, {"category": "A", "data": 2}]

        assert results[1]["group_index"] == 1
        assert results[1]["total_groups"] == 3
        assert results[1]["group_data"] == [{"category": "B", "data": 3}, {"category": "B", "data": 4}]

        assert results[2]["group_index"] == 2
        assert results[2]["total_groups"] == 3
        assert results[2]["group_data"] == [{"category": "C", "data": 5}]

    def test_group_elements_with_filter(self, processor):
        arguments = {
            "key": "category",
            "value": "A",
            "input": [
                {"category": "A", "data": 1},
                {"category": "A", "data": 2},
                {"category": "B", "data": 3},
                {"category": "B", "data": 4},
                {"category": "C", "data": 5},
            ],
        }

        results = list(processor.run(arguments))

        # There should be only one group returned as we're filtering by "A"
        assert len(results) == 1

        # Validate the group data
        assert results[0]["group_index"] == 0
        assert results[0]["total_groups"] == 1
        assert results[0]["group_data"] == [{"category": "A", "data": 1}, {"category": "A", "data": 2}]
