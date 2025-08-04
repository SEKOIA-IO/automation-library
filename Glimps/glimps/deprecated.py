import requests
from requests import Response, Timeout
from sekoia_automation.action import GenericAPIAction
from tenacity import RetryError, Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

base_url = "api/lite/v2/"


class MaxFileSizeExceedError(Exception):
    def __init__(self, msg=None):
        self.message = msg if msg else "The file exceeds the maximum size of 40MB"

    def __str__(self):
        return f"{self.__class__.__name__} {self.message}"


class DeprecatedGlimpsAction(GenericAPIAction):
    def get_headers(self):
        return {
            "Accept": "application/json",
            "X-Auth-Token": self.module.configuration["api_key"],
        }


class DeprecatedRetrieveAnalysis(DeprecatedGlimpsAction):
    name = "[Deprecated] Get the results of an analysis"

    verb: str = "get"
    endpoint: str = base_url + "results/{uuid}"
    query_parameters: list[str] = []


class DeprecatedSearchPreviousAnalysis(DeprecatedGlimpsAction):
    name = "[Deprecated] Search previous analysis"

    verb: str = "get"
    endpoint: str = base_url + "search/{sha256}"
    query_parameters: list[str] = []


class DeprecatedSubmitFileToBeAnalysed(DeprecatedGlimpsAction):
    name = "[Deprecated] Analyse a file"

    endpoint: str = base_url + "submit"
    query_parameters: list[str] = ["bypass-cache"]

    def get_files(self, arguments) -> dict:
        """
        Define the files to supply for the request
        """
        file_name = arguments["file"]
        file_path = self._data_path.joinpath(file_name)
        file_size = file_path.stat().st_size

        if file_size > 40000000:
            raise MaxFileSizeExceedError(msg=f"The file to send exceed the maximum size of 40MB ({file_size})")

        return {"file": (file_name, file_path.open("rb"))}

    def run(self, arguments) -> dict | None:
        headers: dict = self.get_headers()
        url: str = self.get_url(arguments)
        files: dict = self.get_files(arguments)

        # send the request to Glimps
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(5),
                wait=wait_exponential(multiplier=2, min=1, max=10),
                retry=retry_if_exception_type(Timeout),
            ):
                with attempt:
                    response: Response = requests.post(url, files=files, headers=headers, timeout=self.timeout)
        except RetryError:
            self.log_timeout_error(url, arguments)
            return None

        if not response.ok:
            self.log_request_error(url, arguments, response)
            return None
        return response.json()
