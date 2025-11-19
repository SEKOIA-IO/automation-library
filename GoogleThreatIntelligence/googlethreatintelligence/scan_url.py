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

                connector.scan_url(client)
                analysis = connector.results[-1].response
                print("SCAN URL:", analysis)

                # Convert to JSON-serializable dictionary
                # Convert to JSON-serializable dictionary
                serializable_analysis = connector._make_serializable({
                    "id": analysis.id,
                    "type": "analysis",
                    "links": {
                        "self": f"/analyses/{analysis.id}"
                    },
                    "attributes": {
                        "status": analysis.status,
                        "date": getattr(analysis, "date", None),
                        "stats": {
                            "harmless": analysis.stats.get("harmless", 0) if analysis.stats else 0,
                            "malicious": analysis.stats.get("malicious", 0) if analysis.stats else 0,
                            "suspicious": analysis.stats.get("suspicious", 0) if analysis.stats else 0,
                            "undetected": analysis.stats.get("undetected", 0) if analysis.stats else 0,
                            "timeout": analysis.stats.get("timeout", 0) if analysis.stats else 0
                        }
                    }
                })

                return {"success": True, "data": serializable_analysis}

        except Exception as e:
            return {"success": False, "error": str(e)}
