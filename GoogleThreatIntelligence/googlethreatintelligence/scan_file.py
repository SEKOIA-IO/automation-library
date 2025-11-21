"""
Sekoia Automation Action for Google Threat Intelligence: Scan File
"""

from sekoia_automation.action import Action
from .client import VTAPIConnector
import vt
from pathlib import Path


class GTIScanFile(Action):
    """
    Upload a file to Google Threat Intelligence (VirusTotal) for scanning
    """

    def run(self, arguments: dict):
        try:
            api_key = self.module.configuration.get("api_key")
            if not api_key:
                return {"success": False, "error": "API key not configured"}
            file_path = arguments.get("file_path")
            if not file_path or not Path(file_path).exists():
                return {"success": False, "error": f"File not found: {file_path}"}

            connector = VTAPIConnector(api_key, url="", domain="", ip="", file_hash="", cve="")
            with vt.Client(api_key) as client:

                connector.scan_file(client, file_path)
                analysis = connector.results[-1].response
                print(f"API call response: {analysis}")  # Debugging line

            return {"success": True, "data": {"analysis_stats": analysis.stats, "analysis_results": analysis.results, "file_path": file_path}}

        except Exception as e:
            return {"success": False, "error": str(e)}