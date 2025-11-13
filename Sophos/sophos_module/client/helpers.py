from typing import Callable

import requests
import urllib3
from tenacity import Retrying, retry_if_exception_type, retry_if_exception, stop_after_attempt, wait_exponential


def retry_strategy(max_retries: int = 10) -> Retrying:
    """
    Define retry strategy for HTTP requests
    """
    retry_on_status = {429, 500, 502, 503, 504}

    def retry_on_statuses(exception: BaseException) -> bool:
        if isinstance(exception, requests.exceptions.RequestException):
            response = getattr(exception, "response", None)
            # Retry on connection errors and 5xx responses
            if response is None or response.status_code in retry_on_status:
                return True
        return False

    # Return the retry strategy
    return Retrying(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError)
        | retry_if_exception(retry_on_statuses),
        reraise=True,
    )


def retry(max_retries: int = 10) -> Callable:
    """
    Decorator to apply retry strategy to a function
    """

    def wrapper(func) -> Callable:
        strategy = retry_strategy(max_retries=max_retries)
        return strategy.wraps(func)

    return wrapper
