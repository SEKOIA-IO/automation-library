from pydantic import BaseModel


class SSHModuleConfiguration(BaseModel):
    host: str
    port: int = 22
    username: str
    private_key: str | None = None
    passphrase: str | None = None
    password: str | None = None
    host_key_fingerprint: str | None = None
    connect_timeout: int = 15
