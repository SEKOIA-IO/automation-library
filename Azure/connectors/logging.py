import logging
import os


def set_log_level(loggers: set[str], log_level: int) -> None:
    """
    Set the log level for the specified loggers.

    :param loggers: A set of logger names to set the log level for.
    :param log_level: The log level to set for the specified loggers.
    """
    for logger in loggers:
        logging.getLogger(logger.strip()).setLevel(log_level)


def set_log_level_from_env() -> None:
    """
    Set the log level for the specified loggers based on the AZURE_LOG_LEVEL and AZURE_LOGGERS environment variables.

    AZURE_LOG_LEVEL should be set to the desired log level (e.g., 10 for DEBUG, 20 for INFO, etc.).
    AZURE_LOGGERS should be a comma-separated list of logger names to set the log level for. If AZURE_LOGGERS is not set, the log level will be set for all loggers.
    """
    # If AZURE_LOG_LEVEL is not set, do not change the log level for any loggers.
    if os.environ.get("AZURE_LOG_LEVEL") is None:
        return

    loggers = None

    # If AZURE_LOGGERS is set, use the specified loggers. Otherwise, use all loggers.
    if os.environ.get("AZURE_LOGGERS") is not None:
        loggers = set(os.environ.get("AZURE_LOGGERS").split(","))

    # If AZURE_LOGGERS is not set, use all loggers.
    if loggers is None:
        loggers = set(logging.root.manager.loggerDict.keys())

    # Set the log level for the specified loggers.
    set_log_level(loggers, int(os.environ.get("AZURE_LOG_LEVEL")))
