import re
from functools import cached_property
from posixpath import join as urljoin

from sekoia_automation.action import GenericAPIAction


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
