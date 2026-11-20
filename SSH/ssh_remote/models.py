from pydantic import BaseModel, Field


class SSHModuleConfiguration(BaseModel):
    host: str
    port: int = 22
    username: str
    private_key: str | None = Field(None, json_schema_extra={"secret": True})
    passphrase: str | None = Field(None, json_schema_extra={"secret": True})
    password: str | None = Field(None, json_schema_extra={"secret": True})
    host_key_fingerprint: str | None = None
    accept_unknown_host_keys: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)
    connect_timeout: int = 15
