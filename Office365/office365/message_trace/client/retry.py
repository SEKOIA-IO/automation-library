import time

from urllib3.response import HTTPResponse
from urllib3.util.retry import Retry as BaseRetry


class Retry(BaseRetry):
    def get_retry_after(self, response: HTTPResponse) -> float | None:  # type: ignore
        """
        Manage Rate-limiting headers from the server.
        Support standard header Retry-After
        """

        # parse Retry-After header if defined
        retry_after = response.getheader("Retry-After")
        if retry_after:
            return self.parse_retry_after(retry_after)

        return None
