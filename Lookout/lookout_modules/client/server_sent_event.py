import json


class SSEvent:
    """
    Using an event class allows for checking event fields.
    """

    VALID_FIELDS = ["id", "event", "data", "retry"]

    def __init__(self, id: int = None, event: str = "", data: str = "", retry: int = None):
        self.id = id
        self.event = event
        self.data = data
        self.retry = retry

    def blank(self) -> bool:
        """
        Determine if the event is completely blank

        Returns:
            bool: If event is blank
        """
        return not self.id and not self.event and not self.data and not self.retry

    def append(self, field: str, value: str) -> None:
        """
        Add a field/value pair to the event if it is a valid field,
        Otherwise throw a ValueError.

        Args:
            field (str): New field name to add
            value (str): New value for field

        Raises:
            ValueError: On invalid fields.
        """
        if self.__valid_field(field):
            self.__set_field(field, value)
        else:
            raise ValueError(f"'{field}' is not a valid SSE field.")

    def __str__(self) -> str:
        return json.dumps({"id": self.id, "event": self.event, "data": self.data, "retry": self.retry})

    def __valid_field(self, field: str) -> bool:
        """
        Determine if given field name is a valid SSEvent field

        Args:
            field (str): Field name in question

        Returns:
            bool: If field is vaild
        """
        return field in self.VALID_FIELDS

    def __set_field(self, field: str, value: str) -> None:
        """
        Set the event's field to the given value

        Args:
            field (str): SSEvent field name
            value (str): new field value
        """
        if field == "data":
            # for events with multiline data lines, append along with a newline
            self.__dict__[field] += value + "\n"

        elif field == "retry":
            # NOTE: Spec states:
            #   If the field name is "retry" and the field value consists of only ASCII digits,
            #   then interpret the field value as an integer in base ten,
            #   and set the event stream's reconnection time to that integer.
            #   Otherwise, ignore the field.
            # TODO: handle reconnect timing
            self.__dict__[field] = int(value) if value.isdigit() else None
        else:
            self.__dict__[field] = value
