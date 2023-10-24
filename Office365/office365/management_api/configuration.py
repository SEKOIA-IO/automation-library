"""
This module defines the model for intakes configurations.
"""

from sekoia_automation.connector import DefaultConnectorConfiguration


class Office365Configuration(DefaultConnectorConfiguration):
    """Represents an Office 365 intake configuration. It stores data
    required to retrieve data from Microsoft Office 365 Management
    Activity API.

    """

    intake_key: str
    client_secret: str
    uuid: str
    intake_uuid: str
    community_uuid: str
    client_id: str
    publisher_id: str
    tenant_id: str
    content_types: set[str]
