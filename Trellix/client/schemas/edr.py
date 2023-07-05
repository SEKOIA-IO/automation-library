"""Models for EDR data."""
from typing import Generic, TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel

EntityAttributesT = TypeVar("EntityAttributesT", bound=BaseModel)


class TrellixEdrResponse(GenericModel, Generic[EntityAttributesT]):
    """Model to handle trellix edr response."""

    id: str
    type: str
    attributes: EntityAttributesT
