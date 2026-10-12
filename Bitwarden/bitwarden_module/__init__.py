from pydantic import BaseModel
from sekoia_automation.action import Action
from sekoia_automation.module import Module


class BitwardenModule(Module):
    """Bitwarden automation module scaffold."""


class NoopActionArguments(BaseModel):
    """Arguments schema for compliance-only placeholder action."""


class NoopActionResults(BaseModel):
    status: str


class NoopAction(Action):
    name = "Bitwarden noop"
    description = "No-op action used to satisfy automation-library compliance checks"
    module: BitwardenModule
    results_model = NoopActionResults

    def run(self, _arguments: NoopActionArguments) -> dict[str, str]:
        return {"status": "ok"}
