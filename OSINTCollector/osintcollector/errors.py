import traceback


class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class BadConfigurationValue(Error):
    """Exception raised when a configuration value is invalid."""

    pass


class SourceNotExistError(Error):
    """
    Exception raised when a source has never save in objectstorage
    """

    def __init__(self, err, msg):
        self.error = err
        self.message = msg


class ConvertionError(Error):
    """
    Exception raised when convertion type failed
    """

    def __init__(self, typing, source, error):
        self.error = error
        self.source = source
        self.type = typing


class GZipError(Error):
    """
    Exception raised when gzip failed
    """

    def __init__(self, exc_info):
        exc_type, exc_value, exc_traceback = exc_info
        self.traceback = traceback.format_tb(exc_traceback)
        self.type = exc_type.__name__
        self.value = exc_value.args
        self.exc_info = exc_info


class UnzipError(Error):
    """
    Exception raised when unzip failed
    """

    def __init__(self, exc_info):
        exc_type, exc_value, exc_traceback = exc_info
        self.traceback = traceback.format_tb(exc_traceback)
        self.type = exc_type.__name__
        self.value = exc_value.args
        self.exc_info = exc_info


class MagicLibError(Error):
    """
    Exception raised while magic lib is called
    """

    def __init__(self, error):
        self.error = error
