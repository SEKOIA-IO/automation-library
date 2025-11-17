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

        try:
            api_key = self.module.configuration.get("api_key")
            if not api_key:
                return {"success": False, "error": "API key not configured"}
            domain = arguments.get("domain", "")
            ip = arguments.get("ip", "")
            url = arguments.get("url", "")
            file_hash = arguments.get("file_hash", "")

            entity_map = {"domain": domain, "ip": ip, "url": url, "file_hash": file_hash}
            entity_type = next((et for et, value in entity_map.items() if value), "")

            connector = VTAPIConnector(api_key, domain=domain, ip=ip, url=url, file_hash=file_hash)
            with vt.Client(api_key) as client:
                connector.get_comments(client, entity_type, entity_map[entity_type])
                result = connector.results[-1]

            return {"success": result.status == "SUCCESS", "data": result.response}

        except Exception as e:
            return {"success": False, "error": str(e)}
