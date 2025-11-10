"""
Sekoia Automation Action: Get Comments from Google Threat Intelligence
"""
from sekoia_automation.action import Action
from .client import VTAPIConnector
import vt
from typing import Any

class GTIIoCReport(Action):
    """
    Action to get IoC reports from Google Threat Intelligence (VirusTotal)
    Supports: IP addresses, domains, URLs, and file hashes
    """
    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the IoC report action
        
        Arguments:
            ip (str, optional): IP address to query
            domain (str, optional): Domain to query
            url (str, optional): URL to query
            file_hash (str, optional): File hash (MD5, SHA1, or SHA256) to query
            
        Returns:
            dict: IoC report data or error information
        """
        try:
            api_key = self.module.configuration.get("api_key")
            if not api_key:
                return {"success": False, "error": "API key not configured"}
            domain = arguments.get("domain", "")
            ip = arguments.get("ip", "")
            url = arguments.get("url", "")
            file_hash = arguments.get("file_hash", "")

            connector = VTAPIConnector(api_key, domain=domain, ip=ip, url=url, file_hash=file_hash)
            with vt.Client(api_key) as client:
                connector.get_ioc_report(client)
                result = connector.results[-1]

            return {"success": result.status == "SUCCESS", "data": result.response, "error": result.error}

        except Exception as e:
            return {"success": False, "error": str(e)}
