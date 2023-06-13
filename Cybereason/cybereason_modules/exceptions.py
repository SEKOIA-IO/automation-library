from requests import Response


class ConnectorError(Exception):
    def __init__(self, message):
        super().__init__(message)


class TimeoutError(ConnectorError):
    def __init__(self, url: str):
        super().__init__(f"Failed to contact {url} due to a timeout")
        self.url = url


class LoginFailureError(ConnectorError):
    def __init__(self, url: str):
        super().__init__(f"Invalid username/password for {url}")
        self.url = url


class InvalidResponse(ConnectorError):
    def __init__(self, response: Response):
        super().__init__(f"Invalid API response. Got: {response.content.decode('utf-8')}")
        self.response = response


class InvalidJsonResponse(ConnectorError):
    def __init__(self, response: Response):
        super().__init__(
            f"Failed to parse the response from the API. Expected JSON. Got: {response.content.decode('utf-8')}"
        )
        self.response = response
