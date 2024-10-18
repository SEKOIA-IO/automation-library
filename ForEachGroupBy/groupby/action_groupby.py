from sekoia_automation.action import Action


class GroupProcessor(Action):
    """
    Action to groupby element for a list
    """

    def run(self, arguments):
        key = arguments.get("key", 0)  # key to group by
        value = arguments.get("value", None)  # value to filter by, if provided
        input_data = arguments.get("input", [])  # input array of elements

        # Dictionary to hold grouped elements
        grouped = {}

        # Group elements by the specified key
        for element in input_data:
            group_key = element.get(key)
            if group_key not in grouped:
                grouped[group_key] = []
            grouped[group_key].append(element)

        # Prepare to return groups one by one
        total_groups = len(grouped)
        group_index = 0

        # If a value is specified, filter the group
        if value is not None:
            for group_key, elements in grouped.items():
                filtered_elements = [elem for elem in elements if elem.get(key) == value]
                if filtered_elements:
                    yield {"group_index": 0, "total_groups": 1, "group_data": filtered_elements}
        else:
            # If no value is specified, just return all grouped elements
            for group_key, elements in grouped.items():
                yield {"group_index": group_index, "total_groups": total_groups, "group_data": elements}
                group_index += 1
