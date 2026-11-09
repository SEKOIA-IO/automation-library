"""Models for EDR data."""

from typing import Generic, TypeVar

from pydantic import BaseModel

EntityAttributesT = TypeVar("EntityAttributesT", bound=BaseModel)


class Links(BaseModel):
    """Links model."""

    self: str
    first: str
    prev: str
    next: str
    last: str


class TrellixResponse(BaseModel, Generic[EntityAttributesT]):
    """Model to handle trellix response."""

    id: str | None = None
    type: str
    attributes: EntityAttributesT
