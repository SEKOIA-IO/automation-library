class SentinelOneError(Exception):
    pass


class SentinelOneErrorWithStatus(SentinelOneError):
    status: str | None = None


class QueryDeepVisibilityError(SentinelOneErrorWithStatus):
    pass


class QueryDeepVisibilityFailedError(QueryDeepVisibilityError):
    status = "failed"

    def __init__(self, reason: str):
        super().__init__(f"The query has failed: {reason}")


class QueryDeepVisibilityCanceledError(QueryDeepVisibilityError):
    status = "canceled"

    def __init__(self, reason: str):
        super().__init__(f"The query was cancelled: {reason}")


class QueryDeepVisibilityRunningError(QueryDeepVisibilityError):
    status = "running"

    def __init__(self, reason: str):
        super().__init__(f"The query is in progress: {reason}")


class QueryDeepVisibilityTimeoutError(QueryDeepVisibilityError):
    status = "timeout"

    def __init__(self, timeout: int):
        super().__init__(f"The query reached the timeout: {timeout}s")


class RemoteScriptExecutionError(SentinelOneErrorWithStatus):
    pass


class RemoteScriptExecutionFailedError(RemoteScriptExecutionError):
    status = "failed"

    def __init__(self, reason: str):
        super().__init__(f"The remote script execution has failed: {reason}")


class RemoteScriptExecutionCanceledError(RemoteScriptExecutionError):
    status = "canceled"

    def __init__(self, reason: str):
        super().__init__(f"The remote script execution was cancelled: {reason}")


class RemoteScriptExecutionTimeoutError(RemoteScriptExecutionError):
    status = "timeout"

    def __init__(self, timeout: int):
        super().__init__(f"The query reached the timeout: {timeout}s")


class GetMalwaresError(SentinelOneErrorWithStatus):
    pass


class GetMalwaresFailedError(GetMalwaresError):
    status = "failed"

    def __init__(self, reason: str):
        super().__init__(f"The malware retrieval has failed: {reason}")


class GetMalwaresTimeoutError(GetMalwaresError):
    status = "timeout"

    def __init__(self, timeout: int):
        super().__init__(f"The malware retrieval reached the timeout: {timeout}s")
