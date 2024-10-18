import pytest
from utils.action_groupby import GroupProcessor


class TestGroupProcessor:
    @pytest.fixture
    def processor(self):
        return GroupProcessor()

    def test_group_elements_no_filter(self, processor):
        arguments = {
            "group_key": "category",
            "input": [
                {"category": "A", "data": 1},
                {"category": "A", "data": 2},
                {"category": "B", "data": 1},
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
        assert results[1]["group_data"] == [{"category": "B", "data": 1}, {"category": "B", "data": 4}]

        assert results[2]["group_index"] == 2
        assert results[2]["total_groups"] == 3
        assert results[2]["group_data"] == [{"category": "C", "data": 5}]

    def test_group_elements_with_filter_and_value(self, processor):
        arguments = {
            "group_key": "category",
            "filter_key": "data",  # Specify the key to filter on
            "filter_value": 1,  # Specify the value to filter by
            "input": [
                {"category": "A", "data": 1},
                {"category": "A", "data": 2},
                {"category": "B", "data": 1},
                {"category": "B", "data": 4},
                {"category": "C", "data": 5},
            ],
        }

        results = list(processor.run(arguments))

        assert len(results) == 2

        # Validate the group data
        assert results[0]["group_index"] == 0
        assert results[0]["total_groups"] == 2
        assert results[0]["group_data"] == [{"category": "A", "data": 1}]  # Only the element where data is 1

        assert results[1]["group_index"] == 1
        assert results[1]["total_groups"] == 2
        assert results[1]["group_data"] == [{"category": "B", "data": 1}]  # Only the element where data is 1

    def test_group_elements_with_filter(self, processor):
        arguments = {
            "group_key": "category",
            "filter_key": "data",  # Specify the key to filter on
            "input": [
                {"category": "A", "data": 1},
                {"category": "A", "nodata": 2},
                {"category": "B", "data": 1},
                {"category": "B", "nodata": 4},
                {"category": "C", "nodata": 5},
            ],
        }

        results = list(processor.run(arguments))

        assert len(results) == 2

        # Validate the group data
        assert results[0]["group_index"] == 0
        assert results[0]["total_groups"] == 2
        assert results[0]["group_data"] == [{"category": "A", "data": 1}]  # Only the element where data is 1

        assert results[1]["group_index"] == 1
        assert results[1]["total_groups"] == 2
        assert results[1]["group_data"] == [{"category": "B", "data": 1}]  # Only the element where data is 1
