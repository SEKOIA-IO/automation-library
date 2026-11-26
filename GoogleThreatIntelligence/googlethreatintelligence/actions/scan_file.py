"""
Sekoia Automation Action for Google Threat Intelligence: Scan File
"""

from sekoia_automation.action import Action
from ..client import VTAPIConnector
from ..helpers import copy_to_tempfile
import vt
from pathlib import Path


class GTIScanFile(Action):
    """
    Upload a file to Google Threat Intelligence (VirusTotal) for scanning
    """

    def run(self, arguments: dict):
        api_key = self.module.configuration.get("api_key")
        if not api_key:
            return {"success": False, "error": "API key not configured"}

        rel_path = arguments.get("file_path")
        if not rel_path:
            return {"success": False, "error": "Missing argument: file_path"}

        raw_path = Path(rel_path)
        if raw_path.is_absolute():
            # Some playbook runs provide absolute paths that are actually rooted at data_path.
            file_path = raw_path
            if not file_path.exists():
                file_path = self.data_path.joinpath(raw_path.relative_to(raw_path.anchor))
        else:
            file_path = self.data_path.joinpath(raw_path)

        # Verify file exists before attempting upload
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        connector = VTAPIConnector(api_key, url="", domain="", ip="", file_hash="", cve="")

        with copy_to_tempfile(file_path) as tmp_path:
            with vt.Client(api_key, trust_env=True) as client:
                connector.scan_file(client, tmp_path)
                if not connector.results:
                    return {"success": False, "error": "No scan results returned by VT connector"}

                last_result = connector.results[-1]
                analysis = last_result.response
                if analysis is None:
                    return {"success": False, "error": last_result.error or "Scan failed with empty response"}

                return {
                    "success": True,
                    "data": {
                        "analysis_stats": analysis.get("analysis_stats"),
                        "analysis_results": analysis.get("analysis_results"),
                        "file_path": analysis.get("file_path", rel_path),
                    },
                }
