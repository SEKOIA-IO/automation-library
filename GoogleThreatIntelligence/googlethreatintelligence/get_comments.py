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
                if domain != "":
                    connector.get_comments(client, "domain")
                elif ip != "":
                    connector.get_comments(client, "ip")
                elif url != "":
                    connector.get_comments(client, "url")
                elif file_hash != "":
                    connector.get_comments(client, "file")
                else:
                    return {"success": False, "error": "At least one of domain, ip, url, or file_hash must be provided"}

                result = connector.results[-1]

            return {"success": result.status == "SUCCESS", "data": result.response, "error": result.error}

        except Exception as e:
            return {"success": False, "error": str(e)}