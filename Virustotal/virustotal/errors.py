class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class MaxFileSizeExceedError(Error):
    def __init__(self, msg=None):
        self.message = msg if msg else "The file exceeds the maximum size of 200MB"

    def __str__(self):
        return f"{self.__class__.__name__} {self.message}"


class RequestLimitError(Error):
    def __init__(self, msg=None):
        self.message = (
            msg
            if msg
            else "Request rate limit exceeded. You are making more requests than allowed."
            " You have exceeded one of your quotas (minute, daily or monthly)."
            " Daily quotas are reset every day at 00:00 UTC."
        )

    def __str__(self):
        return f"{self.__class__.__name__} {self.message}"


class DuplicateCommentError(Error):
    def __init__(self, msg=None):
        self.message = msg if msg else "Duplicate comment"

    def __str__(self):
        return f"{self.__class__.__name__} {self.message}"
