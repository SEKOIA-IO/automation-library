import re
from functools import cached_property
from uuid import uuid4

import requests
from requests import Response
from sekoia_automation.action import Action


class DownloadFileAction(Action):
    """
    Action to download a file
    """

    @cached_property
    def _http_default_headers(self) -> dict[str, str]:
        """
        Return the default headers for the HTTP requests used in this Action.

        Returns:
            dict[str, str]:
        """
        return {
            "User-Agent": "sekoiaio-connector/{0}-{1}".format(
                self.module.manifest.get("slug"), self.module.manifest.get("version")
            ),
        }

    def _get_headers(self, arguments: dict) -> dict:
        """
        Get headers to use in the requests.

        It merges the argument's headers and the module's ones.
        """
        headers = self.module.configuration.get("headers", {}).copy()
        headers.update(arguments.get("headers", {}))
        headers.update(self._http_default_headers)

        return headers

    def _perform_stream_request(self, arguments: dict) -> Response:
        """
        Perform the request.

        The response will be a stream so it can handle big files.
        """
        headers = self._get_headers(arguments)
        verify = arguments.get("verify_ssl", True)

        r = requests.get(arguments["url"], headers=headers, stream=True, verify=verify)
        r.raise_for_status()
        return r

    def _save_file(self, response: Response) -> dict:
        """
        Save the requests's response in a file.
        """
        filename = self._get_file_name(response)
        file_path = self._data_path / str(uuid4()) / filename

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("wb") as f:
            response.raw.decode_content = True  # Force decoding content
            f.write(response.raw.read())

        return {"file_path": str(file_path)}

    @staticmethod
    def _get_file_name(response: Response) -> str:
        if "Content-Disposition" in response.headers:
            res = re.findall(r'filename="?([^"]+)"?', response.headers["Content-Disposition"])
            if res:
                return res[0]
        return str(uuid4())

    def run(self, arguments: dict) -> dict:
        response = self._perform_stream_request(arguments)
        return self._save_file(response)
