import re
from functools import cached_property
from posixpath import join as urljoin
from typing import Any

import orjson
from sekoia_automation.action import GenericAPIAction
from sekoia_automation.exceptions import MissingActionArgumentError, MissingActionArgumentFileError


class HarfanglabAction(GenericAPIAction):
    endpoint: str

    @cached_property
    def api_token(self):
        return self.module.configuration["api_token"]

    @cached_property
    def base_url(self):
        return self.module.configuration["url"]

    def get_headers(self):
        return {"Authorization": f"Token {self.api_token}"}

    def get_url(self, arguments):
        match = re.findall("{(.*?)}", self.endpoint)
        for replacement in match:
            self.endpoint = self.endpoint.replace(f"{{{replacement}}}", str(arguments.pop(replacement)), 1)

        path = urljoin(self.base_url, self.endpoint.lstrip("/"))

        if self.query_parameters:
            query_arguments: list = []

            for k in self.query_parameters:
                if k in arguments:
                    value = arguments.pop(k)
                    if isinstance(value, bool):
                        value = int(value)
                    query_arguments.append(f"{k}={value}")

            path += f"?{'&'.join(query_arguments)}"
        return path

    def json_argument(self, name: str, arguments: dict, required: bool = True) -> Any:
        """Get a JSON Argument by direct reference of by reading a file.

        If `name` is inside arguments, returns the value.
        If `name`_path is inside arguments, returns the content of the file
        """
        # @todo doesn't work with booleans by default - fix the error in Sekoia SDK
        if arguments.get(name, None) is not None:
            self._result_as_file = False
            return arguments[name]

        elif f"{name}_path" in arguments:
            self._result_as_file = True
            filepath = self.data_path.joinpath(arguments[f"{name}_path"])
            if not filepath.is_file():
                raise MissingActionArgumentFileError(filepath)

            with filepath.open("r") as f:
                return orjson.loads(f.read().encode("utf-8"))

        else:
            if required:
                raise MissingActionArgumentError(name)
