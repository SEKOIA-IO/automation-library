"""
This module defines the model for intakes configurations.
"""

from sekoia_automation.connector import DefaultConnectorConfiguration


class Office365Configuration(DefaultConnectorConfiguration):
    """Represents an Office 365 intake configuration. It stores data
    required to retrieve data from Microsoft Office 365 Management
    Activity API.

    """

    client_id: str
    client_secret: str
    tenant_id: str
