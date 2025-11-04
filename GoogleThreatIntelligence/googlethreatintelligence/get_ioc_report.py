"""
Sekoia Automation Action for Google Threat Intelligence IoC Reports
"""
from typing import Any, Optional
import json
import base64
import vt
from sekoia_automation.action import Action


class GTIIoCReport(Action):
    """
    Action to get IoC reports from Google Threat Intelligence (VirusTotal)
    Supports: IP addresses, domains, URLs, and file hashes
    """
    
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
    
    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the IoC report action
        
        Arguments:
            ip (str, optional): IP address to query
            domain (str, optional): Domain to query
            url (str, optional): URL to query
            file_hash (str, optional): File hash (MD5, SHA1, or SHA256) to query
            
        Returns:
            dict: IoC report data or error information
        """
        try:
            # Get API key from module configuration
            api_key = self.module.configuration.get("api_key")
            if not api_key:
                return {
                    "success": False,
                    "error": "API key not configured in module settings"
                }
            
            # Determine entity type and value
            entity_type, entity = self._get_entity_type_and_value(arguments)
            
            if not entity_type or not entity:
                return {
                    "success": False,
                    "error": "No valid IoC provided. Please provide one of: ip, domain, url, or file_hash"
                }
            
            # Encode URL if needed
            if entity_type == "urls":
                entity_encoded = self._encode_url_id(entity)
            else:
                entity_encoded = entity
            
            # Call VT API using vt-py
            with vt.Client(api_key) as client:
                self.log(f"Querying {entity_type}: {entity}", level="info")
                
                # Get IoC object
                ioc_obj = client.get_object(f"/{entity_type}/{entity_encoded}")
                
                # Extract and format data
                result_data = self._extract_ioc_data(ioc_obj, entity_type, entity)
                
                self.log(f"Successfully retrieved report for {entity}", level="info")
                
                return {
                    "success": True,
                    "data": result_data
                }
        
        except vt.APIError as e:
            error_msg = f"VirusTotal API error: {str(e)}"
            self.log(error_msg, level="error")
            return {
                "success": False,
                "error": error_msg,
                "entity_type": entity_type if entity_type else "unknown",
                "entity": entity if entity else "unknown"
            }
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.log(error_msg, level="error")
            return {
                "success": False,
                "error": error_msg
            }