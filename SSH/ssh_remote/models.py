from pydantic import BaseModel, Field


class SSHModuleConfiguration(BaseModel):
    host: str
    port: int = 22
    username: str
    private_key: str | None = None
    passphrase: str | None = None
    password: str | None = None
    host_key_fingerprint: str | None = None
    accept_unknown_host_keys: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)
    connect_timeout: int = 15
