from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class VaronisModuleConfiguration(BaseModel):
    pass


class VaronisModule(Module):
    configuration: VaronisModuleConfiguration
