import aiohttp


class NozomiError(Exception):
    """
    Custom exception for Nozomi API errors.
    """

    def __init__(self, status_code: int, message: str) -> None:
        """
        Initialize NozomiError with a message and an optional status code.

        Args:
            message: The error message.
            status_code: The HTTP status code associated with the error.
        """
        super().__init__(message)
        self.status_code = status_code

    @classmethod
    async def from_response(cls, response: aiohttp.ClientResponse) -> "NozomiError":  # pragma: no cover
        """
        Create a NozomiError from an aiohttp response.

        Args:
            response: The aiohttp ClientResponse object.

        Returns:
            NozomiError: An instance of NozomiError with the error message and status code.
        """
        text = await response.text()

        if response.status == 401:
            return NozomiAuthError(text)

        return cls(response.status, f"Nozomi API error: {text}")


class NozomiAuthError(NozomiError):
    """
    Custom exception for Nozomi authentication errors.
    """

    def __init__(self, message: str) -> None:
        """
        Initialize NozomiAuthError with a message.

        Args:
            message: The error message.
        """
        super().__init__(status_code=401, message=message)
