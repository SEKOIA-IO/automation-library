"""
Google Threat Intelligence (VirusTotal) API Testing Script
Uses vt-py official library with comprehensive error handling
"""

import vt
import json
import time
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging

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


class VTAPITester:
    """VirusTotal API Testing Class using vt-py"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.results: List[TestResult] = []
        
        # Default test entities
        self.test_domain = "google.com"
        self.test_ip = "8.8.8.8"
        self.test_url = "http://76jdd2ir2embyv47.onion"
        self.test_file_hash = "3ecc0186adba60fb53e9f6c494623dcea979a95c3e66a52896693b8d22f5e18b"  # WanaCry sample
        self.test_cve = "CVE-2021-34527"
    
    def _add_result(self, name: str, method: str, endpoint: str, 
                   status: str, response: Any, error: Optional[str] = None):
        """Add a test result"""
        result = TestResult(name, method, endpoint, status, response, error)
        self.results.append(result)
        
        if error:
            logger.error(f"[{status}] {name}: {error}")
        else:
            logger.info(f"[{status}] {name}: Success")
    
    def test_connectivity(self, client: vt.Client):
        """Test API connectivity"""
        try:
            user = client.get_json("/api/v3/me")
            self._add_result(
                "TEST_CONNECTIVITY",
                "GET",
                "/api/v3/me",
                "SUCCESS",
                {"user_id": user.get("data", {}).get("id")}
            )
        except vt.APIError as e:
            self._add_result(
                "TEST_CONNECTIVITY",
                "GET",
                "/api/v3/me",
                "ERROR",
                None,
                str(e)
            )
    
    def scan_url(self, client: vt.Client):
        """Scan a URL"""
        try:
            analysis = client.scan_url(self.test_url)
            self._add_result(
                "SCAN_URL",
                "POST",
                "/api/v3/urls",
                "SUCCESS",
                {"analysis_id": analysis.id, "url": self.test_url}
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
    
    def get_ip_report(self, client: vt.Client):
        """Get IP address report"""
        try:
            ip = client.get_object(f"/ip_addresses/{self.test_ip}")
            self._add_result(
                "GET_IP_REPORT",
                "GET",
                f"/api/v3/ip_addresses/{self.test_ip}",
                "SUCCESS",
                {
                    "ip": self.test_ip,
                    "country": ip.country if hasattr(ip, 'country') else None,
                    "reputation": ip.reputation if hasattr(ip, 'reputation') else None
                }
            )
        except vt.APIError as e:
            self._add_result(
                "GET_IP_REPORT",
                "GET",
                f"/api/v3/ip_addresses/{self.test_ip}",
                "ERROR",
                None,
                str(e)
            )
    
    def get_domain_report(self, client: vt.Client):
        """Get domain report"""
        try:
            domain = client.get_object(f"/domains/{self.test_domain}")
            self._add_result(
                "GET_DOMAIN_REPORT",
                "GET",
                f"/api/v3/domains/{self.test_domain}",
                "SUCCESS",
                {
                    "domain": self.test_domain,
                    "reputation": domain.reputation if hasattr(domain, 'reputation') else None,
                    "categories": domain.categories if hasattr(domain, 'categories') else None
                }
            )
        except vt.APIError as e:
            self._add_result(
                "GET_DOMAIN_REPORT",
                "GET",
                f"/api/v3/domains/{self.test_domain}",
                "ERROR",
                None,
                str(e)
            )
    
    def get_url_report(self, client: vt.Client):
        """Get URL report"""
        try:
            # URL ID is base64 of URL without padding
            url_id = base64.urlsafe_b64encode(
                self.test_url.encode()
            ).decode().strip("=")
            
            url_obj = client.get_object(f"/urls/{url_id}")
            self._add_result(
                "GET_URL_REPORT",
                "GET",
                f"/api/v3/urls/{url_id}",
                "SUCCESS",
                {
                    "url": self.test_url,
                    "reputation": url_obj.reputation if hasattr(url_obj, 'reputation') else None
                }
            )
        except vt.APIError as e:
            self._add_result(
                "GET_URL_REPORT",
                "GET",
                f"/api/v3/urls/{url_id}",
                "ERROR",
                None,
                str(e)
            )
    
    def get_file_report(self, client: vt.Client):
        """Get file report"""
        try:
            file_obj = client.get_object(f"/files/{self.test_file_hash}")
            self._add_result(
                "GET_FILE_REPORT",
                "GET",
                f"/api/v3/files/{self.test_file_hash}",
                "SUCCESS",
                {
                    "hash": self.test_file_hash,
                    "stats": file_obj.last_analysis_stats if hasattr(file_obj, 'last_analysis_stats') else None
                }
            )
        except vt.APIError as e:
            self._add_result(
                "GET_FILE_REPORT",
                "GET",
                f"/api/v3/files/{self.test_file_hash}",
                "ERROR",
                None,
                str(e)
            )
    
    def get_file_behaviour(self, client: vt.Client):
        """Get file sandbox behavior"""
        try:
            behaviours = client.get_json(
                f"/api/v3/files/{self.test_file_hash}/behaviours"
            )
            self._add_result(
                "GET_FILE_SANDBOX",
                "GET",
                f"/api/v3/files/{self.test_file_hash}/behaviours",
                "SUCCESS",
                {"behaviours_count": len(behaviours.get("data", []))}
            )
        except vt.APIError as e:
            self._add_result(
                "GET_FILE_SANDBOX",
                "GET",
                f"/api/v3/files/{self.test_file_hash}/behaviours",
                "ERROR",
                None,
                str(e)
            )
    
    def get_comments(self, client: vt.Client, entity_type: str = "domains"):
        """Get comments for an entity"""
        try:
            entity = self.test_domain if entity_type == "domains" else self.test_ip
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
        """Get passive DNS resolutions"""
        try:
            resolutions = client.get_json(
                f"/api/v3/domains/{self.test_domain}/resolutions",
                params={"limit": 10}
            )
            self._add_result(
                "PASSIVE_DNS",
                "GET",
                f"/api/v3/domains/{self.test_domain}/resolutions",
                "SUCCESS",
                {"resolutions_count": len(resolutions.get("data", []))}
            )
        except vt.APIError as e:
            self._add_result(
                "PASSIVE_DNS",
                "GET",
                f"/api/v3/domains/{self.test_domain}/resolutions",
                "ERROR",
                None,
                str(e)
            )
    
    def get_vulnerability_report(self, client: vt.Client):
        """Get vulnerability report"""
        try:
            vuln = client.get_json(f"/api/v3/collections/{self.test_cve}")
            self._add_result(
                "VULN_REPORT",
                "GET",
                f"/api/v3/collections/{self.test_cve}",
                "SUCCESS",
                {"cve": self.test_cve, "type": vuln.get("data", {}).get("type")}
            )
        except vt.APIError as e:
            self._add_result(
                "VULN_REPORT",
                "GET",
                f"/api/v3/collections/{self.test_cve}",
                "ERROR",
                None,
                str(e)
            )
    
    def get_vulnerability_associations(self, client: vt.Client):
        """Get vulnerability associations for an entity"""
        try:
            vulns = client.get_json(
                f"/api/v3/ip_addresses/{self.test_ip}/vulnerabilities",
                params={"limit": 10}
            )
            self._add_result(
                "VULN_ASSOCIATIONS",
                "GET",
                f"/api/v3/ip_addresses/{self.test_ip}/vulnerabilities",
                "SUCCESS",
                {"vulnerabilities_count": len(vulns.get("data", []))}
            )
        except vt.APIError as e:
            self._add_result(
                "VULN_ASSOCIATIONS",
                "GET",
                f"/api/v3/ip_addresses/{self.test_ip}/vulnerabilities",
                "ERROR",
                None,
                str(e)
            )
    
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
        
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests: {len(self.results)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {error_count}")
        print(f"{'='*60}\n")


def main():
    """Main execution function"""
    # Security check
    if API_KEY == "REDACTED":
        print("ERROR: Please set VT_API_KEY environment variable")
        print("Example: export VT_API_KEY='your_api_key_here'")
        return
    
    # Initialize tester
    tester = VTAPITester(API_KEY)
    
    # Run tests (optionally provide a test file path)
    # tester.run_all_tests(test_file_path="upload.png")
    tester.run_all_tests()
    
    # Save results
    tester.save_results()


if __name__ == "__main__":
    main()