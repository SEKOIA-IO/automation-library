"""
Models for events attributes.

https://developer.manage.trellix.com/mvision/apis/edr-events
"""
from typing import List

from pydantic import BaseModel


class Privacy(BaseModel):
    """Dto for privacy."""

    maskedAttributes: List[str]


class ConfigEntity(BaseModel):
    """Main entity defines config for AWS."""

    privacy: Privacy
    integrationType: str
    awsKeyId: str
    awsSecretKey: str
    region: str
    bucket: str
    encryptionKey: str
    datasource: str
    filter: str
    subFolder: str
    authType: str
    encryptionType: str
    id: str


class ConfigurationAttributes(BaseModel):
    """ "Model for configuration attributes."""

    emailIds: List[str]
    config: List[ConfigEntity]
