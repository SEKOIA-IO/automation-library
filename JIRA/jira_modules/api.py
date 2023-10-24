from functools import cached_property

from .client import ApiClient


class JiraApi:
    def __init__(self, domain: str, email: str, api_token: str):
        self.domain = domain
        self.email = email
        self.api_token = api_token

    @cached_property
    def client(self):
        return ApiClient(email=self.email, api_token=self.api_token)

    @cached_property
    def base_url(self):
        return "https://%s" % self.domain.replace("https://", "").replace("http://", "")

    def get_json(self, path: str, **kwargs):
        response = self.client.get(f"{self.base_url}/rest/api/3/{path}", timeout=60, **kwargs)
        response.raise_for_status()
        return response.json() if len(response.content) > 0 else None

    def post_json(self, path: str, **kwargs):
        response = self.client.post(f"{self.base_url}/rest/api/3/{path}", timeout=60, **kwargs)
        response.raise_for_status()
        return response.json() if len(response.content) > 0 else None

    def get_paginated_results(self, path: str, result_field: str | None = "values") -> list[dict]:
        start_at = 0
        max_results = 50

        response = self.get_json(path=path, params={"maxResults": max_results, "startAt": start_at})
        is_last = response.get("isLast") if type(response) == dict else False
        if is_last:
            return response.get(result_field) if result_field else response

        result = []
        while True:
            items = response.get(result_field) if result_field else response

            if len(items) == 0:
                break

            result.extend(items)
            start_at += max_results
            response = self.get_json(path=path, params={"maxResults": max_results, "startAt": start_at})

        return result
