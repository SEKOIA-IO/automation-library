"""
Sekoia Automation Action: Get File Behaviour from Google Threat Intelligence
"""
from sekoia_automation.action import Action
from .client import VTAPIConnector
import vt


class GTIGetFileBehaviour(Action):
    """
    Retrieve sandbox (dynamic analysis) behaviour for a file hash
    This action uses is a particular use case of get_ioc_reports from VTAPIConnector with entity_type = files and entity = file_hash, like:
    file = client.get_object("/files/44d88612fea8a8f36de82e1278abb02f")
    Reference: https://virustotal.github.io/vt-py/quickstart.html#get-information-about-a-file
    """

    def run(self, arguments: dict):
        api_key = self.module.configuration.get("api_key")
        file_hash = arguments.get("file_hash", "")

        if not api_key:
            return {"success": False, "error": "API key not configured"}

        try:
            connector = VTAPIConnector(api_key, domain="", ip="", url="", file_hash=file_hash)
            with vt.Client(api_key) as client:
                connector.get_file_behaviour(client)
                result = connector.results[-1]

            return {
                "success": result.status == "SUCCESS",
                "data": result.response
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
