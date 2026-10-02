from typing import Any

from pydantic.v1 import BaseModel

from sentinelone_module.base import SentinelOneAction


class DeleteBlocklistItemActionArguments(BaseModel):
    ids: list[str]


class DeleteBlocklistItemAction(SentinelOneAction):
    name = "Remove Blocklist item"
    description = "Remove item from Blocklist"

    def run(self, arguments: DeleteBlocklistItemActionArguments) -> Any:
        result = self.client.exclusions.delete_black(ids=arguments.ids, type="black_hash")
        return result.json
