from sekoia_automation.action import Action
from typing import Any


class GroupProcessor(Action):
    """
    Action to group items in a list by a specified key and optionally filter them.
    """

    def run(self, arguments: dict):
        group_key = arguments.get("group_key", 0)  # key to group by
        filter_key = arguments.get("filter_key", None)  # key to filter by, if provided
        filter_value = arguments.get("filter_value", None)  # value to filter by, if provided
        input_data = arguments.get("input", [])  # input array of elements

        # Assert that input_data is a list
        assert isinstance(input_data, list), "Input data must be a list"

        grouped: dict[str, Any] = {}

        # Group elements by the specified key
        for element in input_data:
            group_value = element.get(group_key)
            if group_value not in grouped:
                grouped[group_value] = []
            grouped[group_value].append(element)

        # Prepare filtered groups
        filtered_groups = {}

        # Apply filtering to the grouped elements
        for group_value, elements in grouped.items():
            if filter_key is not None:
                if filter_value is not None:
                    filtered_elements = [elem for elem in elements if (elem.get(filter_key) == filter_value)]
                else:
                    filtered_elements = [elem for elem in elements if (elem.get(filter_key) is not None)]
            else:
                filtered_elements = elements

            # Store only non-empty filtered groups
            if filtered_elements:
                filtered_groups[group_value] = filtered_elements

        # Calculate total groups
        total_groups = len(filtered_groups)
        group_index = 0

        response = []
        # Fill each filtered group with appropriate indexing
        for group_value, elements in filtered_groups.items():
            response.append(
                {
                    "group_index": group_index,
                    "total_groups": total_groups,
                    "group_value": group_value,  # Added group_value to the output
                    "group_data": elements,
                }
            )
            group_index += 1
        return {"results": response}
