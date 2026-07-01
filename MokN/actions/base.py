from abc import ABC
from functools import cached_property
from typing import Any

from sekoia_automation.action import Action

from client import ApiClient
from module import MoknModule
from mokn.repositories import AttemptRepository
from mokn.services import AttemptService


class MoknBaseAction(Action, ABC):
    module: MoknModule

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            base_url=self.module.configuration.base_url,
            api_token=self.module.configuration.api_token,
        )

    @cached_property
    def repository(self) -> AttemptRepository:
        return AttemptRepository(
            client=self.client,
            verify_ssl=self.module.configuration.verify_ssl,
        )

    @cached_property
    def service(self) -> AttemptService:
        return AttemptService(repository=self.repository)

    @staticmethod
    def build_result(response: dict[str, Any], default_message: str) -> dict[str, Any]:
        return {
            "status": response.get("status", "success"),
            "message": response.get("message", default_message),
            "data": response.get("data", {}),
        }
