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
            
            
            # Call VT API using vt-py
            with vt.Client(api_key) as client:

                # Determine entity type and value
                entity_type, entity = client._get_entity_type_and_value(arguments)
                
                if not entity_type or not entity:
                    return {
                        "success": False,
                        "error": "No valid IoC provided. Please provide one of: ip, domain, url, or file_hash"
                    }
                
                # Encode URL if needed
                if entity_type == "urls":
                    entity_encoded = client._encode_url_id(entity)
                else:
                    entity_encoded = entity

                self.log(f"Querying {entity_type}: {entity}", level="info")
                
                # Get IoC object
                ioc_obj = client.get_object(f"/{entity_type}/{entity_encoded}")
                
                # Extract and format data
                result_data = client._extract_ioc_data(ioc_obj, entity_type, entity)
                
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