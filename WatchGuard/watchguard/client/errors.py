import aiohttp


class WatchGuardError(Exception):
    """
    Custom exception for WatchGuard API errors.
    """

    def __init__(self, status_code: int, message: str) -> None:
        """
        Initialize WatchGuardError with a message and an optional status code.

        Args:
            message: The error message.
            status_code: The HTTP status code associated with the error.
        """
        super().__init__(message)
        self.status_code = status_code

    @classmethod
    async def from_response(cls, response: aiohttp.ClientResponse) -> "WatchGuardError":
        """
        Create a WatchGuardError from an aiohttp response.

        Args:
            response: The aiohttp ClientResponse object.

        Returns:
            WatchGuardError: An instance of WatchGuardError with the error message and status code.
        """
        text = await response.text()

        if response.status == 401:
            return WatchGuardAuthError(text)

        return cls(response.status, f"WatchGuard API error: {text}")


class WatchGuardAuthError(WatchGuardError):
    """
    Custom exception for WatchGuard authentication errors.
    """

    def __init__(self, message: str) -> None:
        """
        Initialize WatchGuardAuthError with a message.

        Args:
            message: The error message.
        """
        super().__init__(status_code=401, message=message)
