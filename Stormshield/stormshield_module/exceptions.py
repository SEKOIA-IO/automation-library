class StormshieldError(Exception):
    pass


class StormshieldErrorWithStatus(StormshieldError):
    status: str | None = None


class RemoteTaskExecutionError(StormshieldErrorWithStatus):
    pass


class RemoteTaskExecutionFailedError(RemoteTaskExecutionError):
    status = "failed"

    def __init__(self, reason: str):
        super().__init__(f"The remote task execution has failed: {reason}")
