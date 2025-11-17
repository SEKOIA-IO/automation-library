"""
Sekoia Automation Action: Get Comments from Google Threat Intelligence
"""
from sekoia_automation.action import Action
from .client import VTAPIConnector
import vt

class GTIGetComments(Action):
    """
    Retrieve comments for a given domain or IP
    """
    
    def run(self, arguments: dict):
        api_key = self.module.configuration.get("api_key")
        
        try:
            api_key = self.module.configuration.get("api_key")
            if not api_key:
                return {"success": False, "error": "API key not configured"}
            
            # Get entity and entity_type from arguments
            entity = arguments.get("entity", "")
            entity_type = arguments.get("entity_type", "")
            
            if not entity or not entity_type:
                return {"success": False, "error": "Both entity and entity_type are required"}
            
            # Map entity_type to the parameter name expected by VTAPIConnector
            type_map = {
                "domains": "domain",
                "ip_addresses": "ip",
                "urls": "url",
                "files": "file_hash"
            }
            
            param_name = type_map.get(entity_type)
            if not param_name:
                return {"success": False, "error": f"Invalid entity_type: {entity_type}"}
            
            # Create kwargs dict with the appropriate parameter
            connector_kwargs = {param_name: entity}
            
            connector = VTAPIConnector(api_key, **connector_kwargs)
            
            with vt.Client(api_key) as client:
                connector.get_comments(client, entity_type)
            
            result = connector.results[-1]
            
            return {"success": result.status == "SUCCESS", "data": result.response}
            
        except Exception as e:
            return {"success": False, "error": str(e)}