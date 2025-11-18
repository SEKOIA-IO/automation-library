"""
Sekoia Automation Action for Google Threat Intelligence: Scan URL
"""

from sekoia_automation.action import Action
from .client import VTAPIConnector
import vt


class GTIScanURL(Action):
    """
    Submit a URL for scanning to Google Threat Intelligence
    """

    def run(self, arguments: dict):
        try:
            api_key = self.module.configuration.get("api_key")
            if not api_key:
                return {"success": False, "error": "API key not configured"}
            url = arguments.get("url")
            if not url:
                return {"success": False, "error": "No URL provided"}

            connector = VTAPIConnector(api_key, url=url, domain="", ip="", file_hash="", cve="")
            with vt.Client(api_key) as client:
                analysis = connector.scan_url(client)

            if not analysis:
                return {"success": False, "error": "URL scan failed"}

            # Convert to JSON-serializable dictionary
            serializable_analysis = connector._make_serializable({
                "id": analysis.id,
                "type": "analysis",
                "attributes": {
                    "status": analysis.status,
                    "date": getattr(analysis, "date", None),
                    "stats": getattr(analysis, "stats", None)
                },
                "links": {
                    "self": f"/analyses/{analysis.id}"
                }
            })

            return {"success": True, "data": serializable_analysis}

        except Exception as e:
            return {"success": False, "error": str(e)}
