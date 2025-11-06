"""
Sekoia Automation Action for Google Threat Intelligence: Get Passive DNS
"""
from sekoia_automation.action import Action
from .client import VTAPIConnector
import vt


class GTIGetPassiveDNS(Action):
    """
    Retrieve passive DNS records for a domain
    """

    def run(self, arguments: dict):
        try:
            api_key = self.module.configuration.get("api_key")
            if not api_key:
                return {"success": False, "error": "API key not configured"}
            domain = arguments.get("domain", "")

            connector = VTAPIConnector(api_key, domain=domain, ip="", url="", file_hash="")
            with vt.Client(api_key) as client:
                connector.get_passive_dns(client)
                result = connector.results[-1]

            return {"success": result.status == "SUCCESS", "data": result.response, "error": result.error}

        except Exception as e:
            return {"success": False, "error": str(e)}
