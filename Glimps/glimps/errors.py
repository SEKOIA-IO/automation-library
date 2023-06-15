class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class MaxFileSizeExceedError(Error):
    def __init__(self, msg=None):
        self.message = msg if msg else "The file exceeds the maximum size of 40MB"

    def __str__(self):
        return f"{self.__class__.__name__} {self.message}"
