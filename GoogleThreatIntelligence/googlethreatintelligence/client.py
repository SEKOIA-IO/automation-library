"""
Google Threat Intelligence (VirusTotal) API Testing Script
Uses vt-py official library with comprehensive error handling

ACTIONS MAPPING (from requirements):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Action                          | API Endpoint                              | Method(s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scan File                       | POST /api/v3/files                        | scan_file()
                                | POST /api/v3/private/files                |
Get IOC Report                  | GET /api/v3/{entity_type}/{entity}        | get_ioc_report()
  - IP address                  | GET /api/v3/ip_addresses/{ip}             | get_ip_report()
  - URL                         | GET /api/v3/urls/{url_id}                 | get_url_report()
  - Domain                      | GET /api/v3/domains/{domain}              | get_domain_report()
  - File                        | GET /api/v3/files/{hash}                  | get_file_report()
Get Comments                    | GET /api/v3/{entity_type}/{entity}/comments | get_comments()
Get Vulnerability Associations  | GET /api/v3/{entity_type}/{entity}/vulnerabilities | get_vulnerability_associations()
Get File Sandbox Report         | GET /api/v3/files/{hash}/behaviours       | get_file_behaviour()
Scan URL                        | POST /api/v3/urls                         | scan_url()
                                | POST /api/v3/private/urls                 |
Get Curated Associations        | GET /api/v3/{entity_type}/{entity}        | get_ioc_report()
Get Passive DNS Data            | GET /api/v3/{entity_type}/{entity}/resolutions | get_passive_dns()
Get Vulnerability Report        | GET /api/v3/collections/{vuln_id}         | get_vulnerability_report()
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import vt
import base64
from pathlib import Path
from typing import List, Optional, Any
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Security: Load API key from environment variable
import os

API_KEY = os.getenv("VT_API_KEY", "REDACTED")

if API_KEY == "REDACTED":
    logger.warning("API_KEY not set! Set VT_API_KEY environment variable")


@dataclass
class Result:
    """Structure to hold test results"""

    name: str
    method: str
    endpoint: str
    status: str
    response: Any
    error: Optional[str] = None


class VTAPIConnector:
    """VirusTotal API Connector Class using vt-py"""

    def __init__(
        self,
        api_key: str,
        domain: Optional[str] = None,
        ip: Optional[str] = None,
        url: Optional[str] = None,
        file_hash: Optional[str] = None,
        cve: Optional[str] = None,
    ):
        """
        Initialize the VT API Connector

        Args:
            api_key: VirusTotal API key
            domain: Domain to query (optional, defaults to google.com)
            ip: IP address to query (optional, defaults to 8.8.8.8)
            url: URL to query (optional, defaults to sekoia.io)
            file_hash: File hash to query (optional, defaults to EICAR test file)
            cve: CVE ID to query (optional, defaults to CVE-2021-34527)
        """
        self.api_key = api_key
        self.results: List[Result] = []

        # Use provided values when available, otherwise fall back to sensible defaults
        self.domain = domain or "google.com"
        self.ip = ip or "8.8.8.8"
        self.url = url or "https://www.sekoia.io/en/homepage/"
        self.file_hash = file_hash or "44d88612fea8a8f36de82e1278abb02f"  # EICAR test file
        self.cve = cve or "CVE-2021-34527"

        # Headers used by the internal _request helper
        self.headers = {"x-apikey": self.api_key}

    """
    Usage Example:

    connector._add_result(
                "SCAN_URL", "POST", "/api/v3/urls", "SUCCESS", {"analysis_stats": analysis.stats, "analysis_results": analysis.results, "url": self.url}
                )
    """

    def _add_result(
        self, name: str, method: str, endpoint: str, status: str, response: Any, error: Optional[str] = None
    ):
        """Add a result"""
        # Convert VT objects to JSON-serializable format
        if response is not None:
            response = self._make_serializable(response)

        result = Result(name, method, endpoint, status, response, error)
        self.results.append(result)

        if error:
            logger.error(f"[{status}] {name}: {error}")
        else:
            logger.info(f"[{status}] {name}: Success")

    def _make_serializable(self, obj: Any) -> Any:
        """Convert VT objects to JSON-serializable format"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, "__dict__"):
            return str(obj)
        else:
            return obj

    def test_connectivity(self, client: vt.Client):
        """Test API connectivity"""
        try:
            # Use get_object instead of get_json for /me endpoint
            user = client.get_object("/users/me")
            self._add_result(
                "TEST_CONNECTIVITY",
                "GET",
                "/api/v3/users/me",
                "SUCCESS",
                {"user_id": user.id if hasattr(user, "id") else None},
            )
        except vt.APIError as e:
            self._add_result("TEST_CONNECTIVITY", "GET", "/api/v3/users/me", "ERROR", None, str(e))

    def get_ioc_report(self, client: vt.Client, entity_type: str, entity: str):
        """
        Generic IOC Report - handles IP, URL, domain, or file
        GET /api/v3/{entity_type}/{entity}
        """
        try:
            # Handle URL encoding for URLs
            if entity_type == "urls":
                entity = base64.urlsafe_b64encode(entity.encode()).decode().strip("=")

            ioc_obj = client.get_object(f"/{entity_type}/{entity}")

            response_data = {
                "entity_type": entity_type,
                "entity": entity,
                "id": ioc_obj.id if hasattr(ioc_obj, "id") else None,
                "reputation": ioc_obj.reputation if hasattr(ioc_obj, "reputation") else None,
            }

            # Add type-specific attributes
            if hasattr(ioc_obj, "last_analysis_stats"):
                response_data["last_analysis_stats"] = dict(ioc_obj.last_analysis_stats)
            if hasattr(ioc_obj, "country"):
                response_data["country"] = ioc_obj.country
            if hasattr(ioc_obj, "categories"):
                response_data["categories"] = dict(ioc_obj.categories) if ioc_obj.categories else None

            self._add_result(
                f"GET_IOC_REPORT_{entity_type.upper()}",
                "GET",
                f"/api/v3/{entity_type}/{entity}",
                "SUCCESS",
                response_data,
            )
        except vt.APIError as e:
            self._add_result(
                f"GET_IOC_REPORT_{entity_type.upper()}",
                "GET",
                f"/api/v3/{entity_type}/{entity}",
                "ERROR",
                None,
                str(e),
            )

    def get_ip_report(self, client: vt.Client):
        """Get IP address report"""
        self.get_ioc_report(client, "ip_addresses", self.ip)

    def get_domain_report(self, client: vt.Client):
        """Get domain report"""
        self.get_ioc_report(client, "domains", self.domain)

    def get_url_report(self, client: vt.Client):
        """Get URL report"""
        self.get_ioc_report(client, "urls", self.url)

    def get_file_report(self, client: vt.Client):
        """Get file report"""
        self.get_ioc_report(client, "files", self.file_hash)

    def scan_url(self, client: vt.Client):
        """Scan a URL
        This returns an Analysis ID. The analysis can be retrieved by using the Analysis endpoint.
        -> https://docs.virustotal.com/reference/analysis

        """
        try:
            analysis = client.scan_url(self.url, wait_for_completion=True)
            print("Analysis completed")
            # print(analysis.stats)
            # print(analysis.results)
            self._add_result(
                "SCAN_URL",
                "POST",
                "/api/v3/urls",
                "SUCCESS",
                {"analysis_stats": analysis.stats, "analysis_results": analysis.results, "url": self.url},
            )
        except vt.APIError as e:
            self._add_result("SCAN_URL", "POST", "/api/v3/urls", "ERROR", None, str(e))
            return None

    def scan_file(self, client: vt.Client, file_path: str):
        """Scan a file"""
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            with open(file_path, "rb") as f:
                analysis = client.scan_file(f, wait_for_completion=True)
                print("Analysis completed")

            self._add_result(
                "SCAN_FILE",
                "POST",
                "/api/v3/files",
                "SUCCESS",
                {"analysis_stats": analysis.stats, "analysis_results": analysis.results, "file_path": file_path},
            )
        except (vt.APIError, FileNotFoundError, IOError) as e:
            self._add_result("SCAN_FILE", "POST", "/api/v3/files", "ERROR", None, str(e))
            return None

    def get_analysis(self, client: vt.Client, analysis_id: str):
        """Get analysis results"""
        try:
            analysis = client.get_object(f"/analyses/{analysis_id}")
            self._add_result(
                "GET_ANALYSIS",
                "GET",
                f"/api/v3/analyses/{analysis_id}",
                "SUCCESS",
                {"status": analysis.status, "stats": analysis.stats if hasattr(analysis, "stats") else None},
            )
        except vt.APIError as e:
            self._add_result("GET_ANALYSIS", "GET", f"/api/v3/analyses/{analysis_id}", "ERROR", None, str(e))

    def get_file_behaviour(self, client: vt.Client):
        """Get file sandbox behavior"""
        try:
            # Use iterator for behaviours and FULLY consume it
            behaviours_it = client.iterator(f"/files/{self.file_hash}/behaviours", limit=5)

            # IMPORTANT: Fully consume the iterator to test it properly
            behaviours = []
            for behaviour in behaviours_it:
                behaviour_data = {
                    "sandbox_name": behaviour.sandbox_name if hasattr(behaviour, "sandbox_name") else None,
                }

                # Extract detailed behaviour information
                if hasattr(behaviour, "processes_created"):
                    behaviour_data["processes_created"] = len(behaviour.processes_created)
                if hasattr(behaviour, "files_written"):
                    behaviour_data["files_written"] = len(behaviour.files_written)
                if hasattr(behaviour, "files_deleted"):
                    behaviour_data["files_deleted"] = len(behaviour.files_deleted)
                if hasattr(behaviour, "registry_keys_set"):
                    behaviour_data["registry_keys_set"] = len(behaviour.registry_keys_set)
                if hasattr(behaviour, "dns_lookups"):
                    behaviour_data["dns_lookups"] = len(behaviour.dns_lookups)
                if hasattr(behaviour, "ip_traffic"):
                    behaviour_data["ip_traffic"] = len(behaviour.ip_traffic)

                behaviours.append(behaviour_data)

            self._add_result(
                "GET_FILE_SANDBOX",
                "GET",
                f"/api/v3/files/{self.file_hash}/behaviours",
                "SUCCESS",
                {"behaviours_count": len(behaviours), "behaviours": behaviours},
            )
        except vt.APIError as e:
            # This endpoint requires Premium API - log as warning not error
            logger.warning(f"File behaviours not available (may require Premium API): {e}")
            self._add_result(
                "GET_FILE_SANDBOX",
                "GET",
                f"/api/v3/files/{self.file_hash}/behaviours",
                "NOT_AVAILABLE",
                None,
                f"May require Premium API: {str(e)}",
            )

    def get_comments(self, client: vt.Client, entity_type: str, entity: str):
        """Get comments for an entity - FULLY tests the iterator"""
        try:
            # Special case: URLs must be base64url encoded without "=" padding
            if entity_type == "urls":
                import base64

                entity = base64.urlsafe_b64encode(entity.encode()).decode().strip("=")

            path = f"/{entity_type}/{entity}/comments"

            comments_it = client.iterator(path, limit=10)

            comments = []
            for comment in comments_it:
                comments.append(
                    {
                        "text": getattr(comment, "text", None),
                        "date": str(getattr(comment, "date", None)),
                        "votes": {
                            "positive": (
                                getattr(getattr(comment, "votes", {}), "positive", 0)
                                if hasattr(comment, "votes")
                                else 0
                            ),
                            "negative": (
                                getattr(getattr(comment, "votes", {}), "negative", 0)
                                if hasattr(comment, "votes")
                                else 0
                            ),
                        },
                        "author": getattr(comment, "author", None),
                    }
                )

            self._add_result(
                "GET_COMMENTS",
                "GET",
                f"/api/v3/{entity_type}/{entity}/comments",
                "SUCCESS",
                {"comments_count": len(comments), "entity": entity, "comments": comments},
            )

        except vt.APIError as e:
            self._add_result("GET_COMMENTS", "GET", f"/api/v3/{entity_type}/{entity}/comments", "ERROR", None, str(e))

    def get_passive_dns(self, client: vt.Client):
        """Get passive DNS resolutions - FULLY tests the iterator"""
        try:
            # IMPORTANT: Fully consume the iterator to test it properly
            resolutions_it = client.iterator(f"/domains/{self.domain}/resolutions", limit=40)

            resolutions = []
            unique_ips = set()

            for resolution in resolutions_it:
                resolution_data = {
                    "ip_address": resolution.ip_address if hasattr(resolution, "ip_address") else None,
                    "host_name": resolution.host_name if hasattr(resolution, "host_name") else None,
                    "date": str(resolution.date) if hasattr(resolution, "date") else None,
                    "resolver": resolution.resolver if hasattr(resolution, "resolver") else None,
                }
                resolutions.append(resolution_data)

                # Track unique IPs
                if resolution_data["ip_address"]:
                    unique_ips.add(resolution_data["ip_address"])

            self._add_result(
                "PASSIVE_DNS",
                "GET",
                f"/api/v3/domains/{self.domain}/resolutions",
                "SUCCESS",
                {
                    "resolutions_count": len(resolutions),
                    "unique_ips_count": len(unique_ips),
                    "unique_ips": list(unique_ips),
                    "resolutions": resolutions,
                },
            )

            logger.info(
                f"Retrieved and processed {len(resolutions)} DNS resolutions with {len(unique_ips)} unique IPs"
            )

        except vt.APIError as e:
            logger.warning(f"Passive DNS not available (may require Premium API): {e}")
            self._add_result(
                "PASSIVE_DNS",
                "GET",
                f"/api/v3/domains/{self.domain}/resolutions",
                "NOT_AVAILABLE",
                None,
                f"May require Premium API: {str(e)}",
            )

    def get_vulnerability_report(self, client: vt.Client):
        """Get vulnerability report"""
        try:
            # Correct path for vulnerability collections
            # `https://www.virustotal.com/api/v3/collections/vulnerability--cve-2010-3765`
            vuln = client.get_object(f"/collections/vulnerability--{self.cve}")

            vuln_data = {
                "cve": self.cve,
                "id": vuln.id if hasattr(vuln, "id") else None,
            }

            # Extract additional vulnerability details
            if hasattr(vuln, "title"):
                vuln_data["title"] = vuln.title
            if hasattr(vuln, "description"):
                vuln_data["description"] = (
                    vuln.description[:200] + "..." if len(vuln.description) > 200 else vuln.description
                )
            if hasattr(vuln, "cvss"):
                vuln_data["cvss"] = vuln.cvss

            self._add_result(
                "VULN_REPORT",
                "GET",
                f"/api/v3/intelligence/vulnerability_collections/{self.cve}",
                "SUCCESS",
                vuln_data,
            )
        except vt.APIError as e:
            logger.warning(f"OUCH! Vulnerability report not available (may require Premium API): {e}")
            self._add_result(
                "VULN_REPORT",
                "GET",
                f"/api/v3/intelligence/vulnerability_collections/{self.cve}",
                "NOT_AVAILABLE",
                None,
                f"May require Premium API: {str(e)}",
            )

    def get_vulnerability_associations(self, client: vt.Client):
        """Get vulnerability associations for an entity - FULLY tests the iterator"""
        try:
            # IMPORTANT: Fully consume the iterator to test it properly
            vulns_it = client.iterator(f"/ip_addresses/{self.ip}/vulnerabilities", limit=20)

            vulnerabilities = []
            cve_ids = set()
            high_severity_count = 0

            for vuln in vulns_it:
                vuln_data = {
                    "id": vuln.id if hasattr(vuln, "id") else None,
                }

                # Extract CVE information
                if hasattr(vuln, "cve_id"):
                    vuln_data["cve_id"] = vuln.cve_id
                    cve_ids.add(vuln.cve_id)

                if hasattr(vuln, "cvss"):
                    if isinstance(vuln.cvss, dict):
                        vuln_data["cvss_score"] = vuln.cvss.get("score")
                        vuln_data["cvss_severity"] = vuln.cvss.get("severity")
                        if vuln.cvss.get("severity") in ["HIGH", "CRITICAL"]:
                            high_severity_count += 1

                if hasattr(vuln, "description"):
                    vuln_data["description"] = (
                        vuln.description[:150] + "..." if len(vuln.description) > 150 else vuln.description
                    )

                if hasattr(vuln, "published_date"):
                    vuln_data["published_date"] = str(vuln.published_date)

                vulnerabilities.append(vuln_data)

            self._add_result(
                "VULN_ASSOCIATIONS",
                "GET",
                f"/api/v3/ip_addresses/{self.ip}/vulnerabilities",
                "SUCCESS",
                {
                    "vulnerabilities_count": len(vulnerabilities),
                    "unique_cves_count": len(cve_ids),
                    "high_severity_count": high_severity_count,
                    "cve_ids": list(cve_ids),
                    "vulnerabilities": vulnerabilities,
                },
            )

            logger.info(
                f"Retrieved and processed {len(vulnerabilities)} vulnerability associations ({len(cve_ids)} unique CVEs)"
            )

        except vt.APIError as e:
            logger.warning(f"Vulnerability associations not available (may require Premium API): {e}")
            self._add_result(
                "VULN_ASSOCIATIONS",
                "GET",
                f"/api/v3/ip_addresses/{self.ip}/vulnerabilities",
                "NOT_AVAILABLE",
                None,
                f"May require Premium API: {str(e)}",
            )
