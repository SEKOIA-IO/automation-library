class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class MissingAPIkey(Error):
    def __init__(self, msg=None):
        self.message = msg if msg else "The endpoint you are requesting requires an API key"

    def __str__(self):
        return f"{self.__class__.__name__} {self.message}"
