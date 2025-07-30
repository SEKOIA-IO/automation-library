from sekoia_automation.action import Action
from typing import Dict
from posixpath import join as urljoin
from ..helpers import stix_to_indicators
from collections import defaultdict
from ..models import GetBlockListActionRequest, GetBlockListActionResponse, ItemsModel, RuleModel, HashModel, PathModel
from .get_block_list_action import GetBlockListAction

class PushIocsAction(Action):
    SUPPORTED_TYPES_MAP: Dict[str, Dict[str, str]] = {
        "ipv4-addr": {"value": "IPV4"},
        "ipv6-addr": {"value": "IPV6"},
        "file": {"hashes.MD5": "md5", "hashes.SHA256": "sha256"},
    }
    
    def indicator_to_rule(self, type:str, value:str) -> RuleModel:
        """
        Convert an indicator to a RuleModel.
        """
        match type:
            case "hash":
                model = HashModel()
                return model
            case "path":
                model = PathModel()
                return model
            case _:
                return {}
            
            
        

    def get_existing_indicators(self) -> list[ItemsModel]:
        page = 1
        existing_indicators: list[ItemsModel] = []
        block_list_request = GetBlockListActionRequest(page=page, per_page=100)
        get_block_list_action = GetBlockListAction()
        block_list_response: GetBlockListActionResponse = get_block_list_action.run(block_list_request)
        nb_pages = block_list_response.pages_count
        if page >= nb_pages:
            return block_list_response.items
        page += 1
        while page <= nb_pages:
            block_list_request.page = page
            block_list_response = get_block_list_action.run(block_list_request)
            existing_indicators.extend(block_list_response.items)
            page += 1
        return existing_indicators
    
    def get_valid_indicators(self, stix_objects, existing_indicators: list[ItemsModel]) -> Dict[str, list]:

        seen_values = defaultdict(list)
        results = {"valid": [], "revoked": []}
        for object in stix_objects:
            # Extract value and type from pattern
            self.log(message=f"object in stix_objects {str(object)}", level="debug")
            indicators = stix_to_indicators(stix_object=object, supported_types_map=self.SUPPORTED_TYPES_MAP)
            for indicator in indicators:
                ioc_value = indicator["value"]
                ioc_type = indicator["type"]
                result = self.indicator_to_rule(type=ioc_type, value=ioc_value)

                # Handle revoked objects
                if object.get("revoked", False):
                    results["revoked"].append(result)
                    continue

                # Ignore this IOC if the same value has already been processed
                if ioc_value in seen_values[ioc_type]:
                    continue

                seen_values[ioc_type].append(ioc_value)
                results["valid"].append(result)

        return results

    def run(self, arguments: dict) -> dict:
        stix_objects = self.json_argument("stix_objects", arguments)
        if stix_objects is None or len(stix_objects) == 0:
            self.log("Received stix_objects were empty")

        existing_indicators = self.get_existing_indicators()

        indicators = self.get_valid_indicators(stix_objects, existing_indicators)
        if len(indicators["valid"]) == 0 and len(indicators["revoked"]) == 0:
            self.log("Received indicators were not valid and/or not supported")
            return
        
        # Remove revoked indicators before proceeding with adding new ones
        pass
