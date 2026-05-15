from pydantic.v1 import BaseModel, Field


class BlockIPAddressArguments(BaseModel):
    ip_address: str = Field(..., description="IPv4 or IPv6 address to block")
    duration_s: int = Field(..., description="Duration in seconds for which the IP should be blocked")
