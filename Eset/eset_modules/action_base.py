from abc import ABC
from datetime import datetime, timedelta, timezone
from functools import cached_property

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
    def get_expire_time(task_expire_time: int) -> str:
        expire_time = datetime.now().astimezone(timezone.utc) + timedelta(minutes=task_expire_time)
        return expire_time.strftime("%Y-%m-%dT%H:%M:%SZ")
