from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer


class BrevoHttpModuleConfiguration(BaseModel):
    api_key: str = Field(..., description="API Key", json_schema_extra={"secret": True})


class BrevoApiLog(BaseModel):
    model_config = ConfigDict(strict=True)

    action: str
    date: str
    user_agent: str
    user_email: str
    user_ip: str

    @model_serializer(mode="wrap", when_used="json")
    def serialize_model(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        serialized = handler(self)
        serialized["source"] = "brevo"
        return serialized


class BrevoApiData(BaseModel):
    logs: list[BrevoApiLog] = Field()
    count: int = Field()
