from pydantic import BaseModel, Field
from sekoia_automation.module import Module



class FakeAssetModuleConfiguration(BaseModel):
    len_data_to_send: str = Field(..., description="Number of data to send")
    time_sleep: str = Field(..., description="Time to sleep")


class FakeAssetModule(Module):
    configuration: FakeAssetModuleConfiguration