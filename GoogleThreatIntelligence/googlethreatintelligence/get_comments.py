"""
Sekoia Automation Action: Get Comments from Google Threat Intelligence
"""

from sekoia_automation.action import Action
from .client import VTAPIConnector
import vt


class GTIGetComments(Action):
    """
    Retrieve comments for a given domain or IP
    """

    def run(self, arguments: dict):
        api_key = self.module.configuration.get("api_key")
        entity_type = arguments.get("entity_type", "domains")
        entity = arguments.get("entity")

        if not api_key:
            return {"success": False, "error": "API key not configured"}

        if not entity:
            return {"success": False, "error": "Entity parameter is required"}

        try:
            connector = VTAPIConnector(
                api_key=api_key,
                domain=entity if entity_type == "domains" else None,
                ip=entity if entity_type == "ip_addresses" else None,
            )

            with vt.Client(api_key) as client:
                connector.get_comments(client, entity_type)
                # Get the last result from the connector
                result = connector.results[-1]

            return {"success": result.status == "SUCCESS", "data": result.response}

        except Exception as e:
            return {"success": False, "error": str(e)}
