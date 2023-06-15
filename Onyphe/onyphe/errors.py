class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class InvalidArgument(Error):
    def __init__(self, msg=None, arg_type="argument", value=None, value_type=None):
        self.message = msg if msg else f"The {arg_type} you are requesting information on is not a valid {arg_type}"
        self.value = value
        self.value_type = value_type

    def __str__(self):
        return f"{self.__class__.__name__} ({self.value}:{self.value_type}) {self.message}"


class MissingAPIkey(Error):
    def __init__(self, msg=None):
        self.message = msg if msg else "The endpoint you are requesting requires an API key"

    def __str__(self):
        return f"{self.__class__.__name__} {self.message}"
