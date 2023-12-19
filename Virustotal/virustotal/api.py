from posixpath import join as urljoin

import requests


class VirusTotalV3API:
    VTAPI_BASE_URL = "https://www.virustotal.com/api/v3/"

    def request(self, method, url, json=None, headers=None):
        if headers is None:
            headers = {}

        headers["x-apikey"] = self.module.configuration["apikey"]

        return requests.request(method, urljoin(self.VTAPI_BASE_URL, url.lstrip("/")), json=json, headers=headers)
