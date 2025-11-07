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
import json
import time
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging
import requests
import urllib.parse
import validators


logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security: Load API key from environment variable
import os
API_KEY = os.getenv("VT_API_KEY", "REDACTED")

if API_KEY == "REDACTED":
    logger.warning("API_KEY not set! Set VT_API_KEY environment variable")

@dataclass
class TestResult:
    """Structure to hold test results"""
    name: str
    method: str
    endpoint: str
    status: str
    response: Any
    error: Optional[str] = None


class VTAPIConnector:
    """VirusTotal API Class using vt-py"""
    
    def __init__(self, api_key: str, domain: str, ip: str, url: str, file_hash: str, cve: str):
        self.api_key = api_key
        self.results: List[TestResult] = []
        
        self.domain = "google.com"
        self.ip = "8.8.8.8"
        self.url = "https://www.sekoia.io/en/homepage/"
        self.file_hash = "44d88612fea8a8f36de82e1278abb02f"
        self.cve = "CVE-2021-34527"

    # ---- Helpers ----

    def _request(self, path: str, params: dict = None):
        """Perform a GET request and handle common errors."""
        url = urllib.parse.urljoin(self.host + "/", path.lstrip("/"))
        logger.debug(f"Requesting URL: {url}")

        try:
            resp = requests.get(url, headers=self.headers, params=params)
            if resp.status_code == 404:
                logger.warning("Resource not found: %s", path)
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error for {path}: {e}")
            return {"error": {"message": str(e), "status_code": resp.status_code}}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception for {path}: {e}")
            return {"error": {"message": str(e)}}


    @staticmethod
    def _entity_endpoint(entity_type: str):
        mapping = {
            "ip": "ip_addresses",
            "domain": "domains",
            "url": "urls",
            "file_hash": "files"
        }
        return mapping.get(entity_type, entity_type)

    def _get_entity_type_and_value(self, arguments: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Determine entity type and value from arguments
        Priority: ip > domain > url > file_hash
        """
        if arguments.get("ip"):
            return "ip_addresses", arguments["ip"]
        elif arguments.get("domain"):
            return "domains", arguments["domain"]
        elif arguments.get("url"):
            return "urls", arguments["url"]
        elif arguments.get("file_hash") or arguments.get("hash"):
            hash_value = arguments.get("file_hash") or arguments.get("hash")
            return "files", hash_value
        
        return None, None
    
    def _encode_url_id(self, url: str) -> str:
        """Encode URL to base64 format required by VT API"""
        return base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    
    def _extract_ioc_data(self, ioc_obj: Any, entity_type: str, entity: str) -> dict[str, Any]:
        """Extract relevant data from VT IoC object"""
        data = {
            "entity_type": entity_type,
            "entity": entity,
            "id": ioc_obj.id if hasattr(ioc_obj, 'id') else None,
        }
        
        # Common attributes
        if hasattr(ioc_obj, 'reputation'):
            data["reputation"] = ioc_obj.reputation
        
        if hasattr(ioc_obj, 'last_analysis_stats'):
            data["last_analysis_stats"] = dict(ioc_obj.last_analysis_stats)
        
        if hasattr(ioc_obj, 'last_analysis_results'):
            # Summarize analysis results
            results = ioc_obj.last_analysis_results
            data["detections"] = {
                "malicious": sum(1 for r in results.values() if r.get("category") == "malicious"),
                "suspicious": sum(1 for r in results.values() if r.get("category") == "suspicious"),
                "undetected": sum(1 for r in results.values() if r.get("category") == "undetected"),
                "harmless": sum(1 for r in results.values() if r.get("category") == "harmless"),
            }
        
        # IP-specific attributes
        if entity_type == "ip_addresses":
            if hasattr(ioc_obj, 'country'):
                data["country"] = ioc_obj.country
            if hasattr(ioc_obj, 'asn'):
                data["asn"] = ioc_obj.asn
            if hasattr(ioc_obj, 'as_owner'):
                data["as_owner"] = ioc_obj.as_owner
        
        # Domain-specific attributes
        elif entity_type == "domains":
            if hasattr(ioc_obj, 'categories'):
                data["categories"] = dict(ioc_obj.categories) if ioc_obj.categories else None
            if hasattr(ioc_obj, 'last_dns_records'):
                data["dns_records_count"] = len(ioc_obj.last_dns_records)
        
        # URL-specific attributes
        elif entity_type == "urls":
            if hasattr(ioc_obj, 'url'):
                data["url"] = ioc_obj.url
            if hasattr(ioc_obj, 'title'):
                data["title"] = ioc_obj.title
        
        # File-specific attributes
        elif entity_type == "files":
            if hasattr(ioc_obj, 'sha256'):
                data["sha256"] = ioc_obj.sha256
            if hasattr(ioc_obj, 'md5'):
                data["md5"] = ioc_obj.md5
            if hasattr(ioc_obj, 'sha1'):
                data["sha1"] = ioc_obj.sha1
            if hasattr(ioc_obj, 'size'):
                data["size"] = ioc_obj.size
            if hasattr(ioc_obj, 'type_description'):
                data["type_description"] = ioc_obj.type_description
            if hasattr(ioc_obj, 'meaningful_name'):
                data["meaningful_name"] = ioc_obj.meaningful_name
        
        return data
    

    def _add_result(self, name: str, method: str, endpoint: str, 
                   status: str, response: Any, error: Optional[str] = None):
        """Add a result"""
        # Convert VT objects to JSON-serializable format
        if response is not None:
            response = self._make_serializable(response)
        
        result = TestResult(name, method, endpoint, status, response, error)
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
        elif hasattr(obj, '__dict__'):
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
                {"user_id": user.id if hasattr(user, 'id') else None}
            )
        except vt.APIError as e:
            self._add_result(
                "TEST_CONNECTIVITY",
                "GET",
                "/api/v3/users/me",
                "ERROR",
                None,
                str(e)
            )

    # ---- Core API methods ----

    def get_comments(self, arguments: dict):
        """Get comments for an entity"""
        entity_type, entity = self._get_entity_type_and_value(arguments)
        path = f"/v1/{self._entity_endpoint(entity_type)}/{entity}/comments"
        return self._request(path)

    def get_passive_dns(self, arguments: dict):
        """Get passive DNS resolutions"""
        entity_type, entity = self._get_entity_type_and_value(arguments)
        path = f"/v1/{self._entity_endpoint(entity_type)}/{entity}/resolutions"
        return self._request(path)

    def get_vulnerability_associations(self, arguments: dict):
        """Get vulnerability associations for an entity"""
        entity_type, entity = self._get_entity_type_and_value(arguments)
        path = f"/v1/{self._entity_endpoint(entity_type)}/{entity}/vulnerabilities"
        return self._request(path)
 
    def scan_url(self, client: vt.Client):
        """Scan a URL"""
        try:
            analysis = client.scan_url(self.url)
            self._add_result(
                "SCAN_URL",
                "POST",
                "/api/v3/urls",
                "SUCCESS",
                {"analysis_id": analysis.id, "url": self.url}
            )
            return analysis.id
        except vt.APIError as e:
            self._add_result(
                "SCAN_URL",
                "POST",
                "/api/v3/urls",
                "ERROR",
                None,
                str(e)
            )
            return None
    
    def scan_file(self, client: vt.Client, file_path: str):
        """Scan a file"""
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(file_path, "rb") as f:
                analysis = client.scan_file(f)
            
            self._add_result(
                "SCAN_FILE",
                "POST",
                "/api/v3/files",
                "SUCCESS",
                {"analysis_id": analysis.id, "file": file_path}
            )
            return analysis.id
        except (vt.APIError, FileNotFoundError, IOError) as e:
            self._add_result(
                "SCAN_FILE",
                "POST",
                "/api/v3/files",
                "ERROR",
                None,
                str(e)
            )
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
                {
                    "status": analysis.status,
                    "stats": analysis.stats if hasattr(analysis, 'stats') else None
                }
            )
        except vt.APIError as e:
            self._add_result(
                "GET_ANALYSIS",
                "GET",
                f"/api/v3/analyses/{analysis_id}",
                "ERROR",
                None,
                str(e)
            )
    
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
                "id": ioc_obj.id if hasattr(ioc_obj, 'id') else None,
                "reputation": ioc_obj.reputation if hasattr(ioc_obj, 'reputation') else None,
            }
            
            # Add type-specific attributes
            if hasattr(ioc_obj, 'last_analysis_stats'):
                response_data["last_analysis_stats"] = dict(ioc_obj.last_analysis_stats)
            if hasattr(ioc_obj, 'country'):
                response_data["country"] = ioc_obj.country
            if hasattr(ioc_obj, 'categories'):
                response_data["categories"] = dict(ioc_obj.categories) if ioc_obj.categories else None
            
            self._add_result(
                f"GET_IOC_REPORT_{entity_type.upper()}",
                "GET",
                f"/api/v3/{entity_type}/{entity}",
                "SUCCESS",
                response_data
            )
        except vt.APIError as e:
            self._add_result(
                f"GET_IOC_REPORT_{entity_type.upper()}",
                "GET",
                f"/api/v3/{entity_type}/{entity}",
                "ERROR",
                None,
                str(e)
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
    
    def get_file_behaviour(self, client: vt.Client):
        """Get file sandbox behavior"""
        try:
            # Use iterator for behaviours
            behaviours_it = client.iterator(
                f"/files/{self.file_hash}/behaviours",
                limit=5
            )
            behaviours = list(behaviours_it)
            
            self._add_result(
                "GET_FILE_SANDBOX",
                "GET",
                f"/api/v3/files/{self.file_hash}/behaviours",
                "SUCCESS",
                {"behaviours_count": len(behaviours)}
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
                f"May require Premium API: {str(e)}"
            )
    """
    def get_comments(self, client: vt.Client, entity_type: str = "domains"):
        try:
            entity = self.domain if entity_type == "domains" else self.ip
            comments_it = client.iterator(
                f"/{entity_type}/{entity}/comments",
                limit=5
            )
            comments = [{"text": c.text, "date": c.date} for c in comments_it]
            
            self._add_result(
                "GET_COMMENTS",
                "GET",
                f"/api/v3/{entity_type}/{entity}/comments",
                "SUCCESS",
                {"comments_count": len(comments), "entity": entity}
            )
        except vt.APIError as e:
            self._add_result(
                "GET_COMMENTS",
                "GET",
                f"/api/v3/{entity_type}/{entity}/comments",
                "ERROR",
                None,
                str(e)
            )
    def get_passive_dns(self, client: vt.Client):
        try:
            # Use iterator for resolutions
            resolutions_it = client.iterator(
                f"/domains/{self.domain}/resolutions",
                limit=10
            )
            resolutions = list(resolutions_it)
            
            self._add_result(
                "PASSIVE_DNS",
                "GET",
                f"/api/v3/domains/{self.domain}/resolutions",
                "SUCCESS",
                {"resolutions_count": len(resolutions)}
            )
        except vt.APIError as e:
            logger.warning(f"Passive DNS not available (may require Premium API): {e}")
            self._add_result(
                "PASSIVE_DNS",
                "GET",
                f"/api/v3/domains/{self.domain}/resolutions",
                "NOT_AVAILABLE",
                None,
                f"May require Premium API: {str(e)}"
            )
     """
    def get_vulnerability_report(self, client: vt.Client):
        """Get vulnerability report"""
        try:
            # Correct path for vulnerability collections
            vuln = client.get_object(f"/intelligence/vulnerability_collections/{self.cve}")
            self._add_result(
                "VULN_REPORT",
                "GET",
                f"/api/v3/intelligence/vulnerability_collections/{self.cve}",
                "SUCCESS",
                {"cve": self.cve, "id": vuln.id if hasattr(vuln, 'id') else None}
            )
        except vt.APIError as e:
            logger.warning(f"Vulnerability report not available (may require Premium API): {e}")
            self._add_result(
                "VULN_REPORT",
                "GET",
                f"/api/v3/intelligence/vulnerability_collections/{self.cve}",
                "NOT_AVAILABLE",
                None,
                f"May require Premium API: {str(e)}"
            )
    """ 
    def get_vulnerability_associations(self, client: vt.Client):
        try:
            # Use iterator for vulnerabilities
            vulns_it = client.iterator(
                f"/ip_addresses/{self.ip}/vulnerabilities",
                limit=10
            )
            vulns = list(vulns_it)
            
            self._add_result(
                "VULN_ASSOCIATIONS",
                "GET",
                f"/api/v3/ip_addresses/{self.ip}/vulnerabilities",
                "SUCCESS",
                {"vulnerabilities_count": len(vulns)}
            )
        except vt.APIError as e:
            logger.warning(f"Vulnerability associations not available (may require Premium API): {e}")
            self._add_result(
                "VULN_ASSOCIATIONS",
                "GET",
                f"/api/v3/ip_addresses/{self.ip}/vulnerabilities",
                "NOT_AVAILABLE",
                None,
                f"May require Premium API: {str(e)}"
            )
    """
    def run_all_tests(self, test_file_path: Optional[str] = None):
        """Run all API tests"""
        logger.info("Starting VirusTotal API tests...")
        
        with vt.Client(self.api_key) as client:
            # Basic connectivity
            self.test_connectivity(client)
            time.sleep(0.5)
            
            # IOC Reports
            self.get_ip_report(client)
            time.sleep(0.5)
            
            self.get_domain_report(client)
            time.sleep(0.5)
            
            self.get_url_report(client)
            time.sleep(0.5)
            
            self.get_file_report(client)
            time.sleep(0.5)
            
            # Scans
            analysis_id = self.scan_url(client)
            time.sleep(1)
            
            if analysis_id:
                self.get_analysis(client, analysis_id)
                time.sleep(0.5)
            
            # File scan (optional)
            if test_file_path:
                file_analysis_id = self.scan_file(client, test_file_path)
                time.sleep(1)
                if file_analysis_id:
                    self.get_analysis(client, file_analysis_id)
                    time.sleep(0.5)
            
            # Additional data
            self.get_comments(client)
            time.sleep(0.5)
            
            self.get_file_behaviour(client)
            time.sleep(0.5)
            
            self.get_passive_dns(client)
            time.sleep(0.5)
            
            self.get_vulnerability_report(client)
            time.sleep(0.5)
            
            self.get_vulnerability_associations(client)
        
        logger.info("All tests completed!")
    
    def save_results(self, output_file: str = "vt_test_results.json"):
        """Save test results to JSON file"""
        results_dict = [asdict(r) for r in self.results]
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {output_file}")
        
        # Print summary
        success_count = sum(1 for r in self.results if r.status == "SUCCESS")
        error_count = sum(1 for r in self.results if r.status == "ERROR")
        not_available_count = sum(1 for r in self.results if r.status == "NOT_AVAILABLE")
        
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests: {len(self.results)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {error_count}")
        print(f"Not Available (Premium API): {not_available_count}")
        print(f"{'='*60}\n")

"""
if __name__ == "__main__":
    # Security check
    if API_KEY == "REDACTED":
        print("ERROR: Please set VT_API_KEY environment variable")
        print("Example: export VT_API_KEY='your_api_key_here'")
        return
    
    # Initialize tester
    tester = VTAPIConnector(API_KEY)
    
    # Run tests (optionally provide a test file path)
    # tester.run_all_tests(test_file_path="upload.png")
    tester.run_all_tests()
    
    # Save results
    tester.save_results()
"""