import requests


class StreamError(Exception):
    pass


class StreamNotAvailable(StreamError):
    def __init__(self, response: requests.Response):
        super().__init__(f"Stream is not available, http.status_code={response.status_code}")
