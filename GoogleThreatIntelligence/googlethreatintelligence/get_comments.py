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
            with vt.Client(api_key, trust_env=True) as client:
                # Determine which entity to query for comments
                # Priority: domain > ip > url > file_hash
                # Only one can be provided at a time because of input constraints
                entity_type = None
                entity_name = None

                if domain != "":
                    entity_type = "domains"
                    entity_name = domain
                elif ip != "":
                    entity_type = "ip_addresses"
                    entity_name = ip
                elif url != "":
                    entity_type = "urls"
                    entity_name = url
                elif file_hash != "":
                    entity_type = "files"
                    entity_name = file_hash
                else:
                    # Use default domain
                    entity_type = "domains"
                    entity_name = domain

                connector.get_comments(client, entity_type, entity_name)

                result = connector.results[-1]

            return {"success": result.status == "SUCCESS", "data": result.response, "error": result.error}

        except Exception as e:
            return {"success": False, "error": str(e)}
