from abc import ABC
from datetime import datetime, timedelta, timezone
from functools import cached_property

import requests
from sekoia_automation.action import Action

from . import EsetModule
from .client import ApiClient


class EsetBaseAction(Action, ABC):
    module: EsetModule

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            auth_base_url=f"https://{self.module.configuration.region}.business-account.iam.eset.systems",
            username=self.module.configuration.username,
            password=self.module.configuration.password,
        )

    @staticmethod
    def get_create_time() -> str:
        create_time = datetime.now().astimezone(timezone.utc)
        return create_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def prepare_result(response: requests.Response) -> dict:
        return {"status_code": response.status_code, "body": response.json() if len(response.content) > 0 else ""}
