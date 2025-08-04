from ..base import BitdefenderAction
from typing import Dict
from ..helpers import stix_to_indicators, parse_get_block_list_response
from collections import defaultdict
from ..models import (
    GetBlockListActionRequest,
    GetBlockListActionResponse,
    ItemsModel,
    RuleModel,
    HashModel,
    ConnectionModel,
    RemoteAddressModel,
    LocalAddressModel,
    BlockListModel,
    RemoveBlockActionRequest,
    DirectlyConnectedModel,
)
from ..bitdefender_gravity_zone_api import (
    prepare_push_block_endpoint,
    prepare_remove_block_endpoint,
    prepare_get_block_list_endpoint,
)


### Non used action (for the moment) until api bitdefender rate limiting change ###
class PushIocsAction(BitdefenderAction):
    SUPPORTED_TYPES_MAP: Dict[str, Dict[str, str]] = {
        "ipv4-addr": {"value": "IPV4"},
        "ipv6-addr": {"value": "IPV6"},
        "file": {"hashes.MD5": "md5", "hashes.SHA256": "sha256"},
    }

    def indicator_to_rule(self, type: str, value: str, path: list[str]) -> RuleModel:
        """
        Convert an indicator to a RuleModel.
        """
        details = None
        match type:
            case "file":
                if "MD5" in path or "MD5" in (p.replace("-", "") for p in path):
                    details = HashModel(algorithm="md5", hash=value)
                if "SHA-256" in path or "SHA256" in path:
                    details = HashModel(algorithm="sha256", hash=value)
            case "ipv4-addr":
                localAddress = LocalAddressModel(any=True)
                remoteAddress = RemoteAddressModel(any=False, ip_mask=value)
                directlyConnected = DirectlyConnectedModel(enable=False)
                details = ConnectionModel(
                    rule_name=f"{value}",
                    ip_version="IPV4",
                    protocol="any",
                    direction="both",
                    local_address=localAddress,
                    remote_address=remoteAddress,
                    directly_connected=directlyConnected,
                )
            case "ipv6-addr":
                localAddress = LocalAddressModel(any=True)
                remoteAddress = RemoteAddressModel(any=False, ip_mask=value)
                directlyConnected = DirectlyConnectedModel(enable=False)
                details = ConnectionModel(
                    rule_name=f"{value}",
                    ip_version="IPV6",
                    protocol="any",
                    direction="both",
                    local_address=localAddress,
                    remote_address=remoteAddress,
                    directly_connected=directlyConnected,
                )
            case _:
                return None

        if details is None:
            return None

        return RuleModel(details=details)

    def itemsModelList_to_rules(self, items: list[ItemsModel]) -> list[RuleModel]:
        """
        Convert a list of ItemsModel to a list of RuleModel.
        """
        rules = []
        for item in items:
            rule = self.itemsModel_to_rule(item)
            if rule is not None:
                rules.append(rule)
        return rules

    def itemsModel_to_rule(self, item: ItemsModel) -> RuleModel:
        """
        Convert an ItemsModel to a RuleModel.
        """
        return RuleModel(details=item.details)

    def get_existing_rules(self) -> list[ItemsModel]:
        page = 1
        existing_indicators: list[ItemsModel] = []
        block_list_request = GetBlockListActionRequest(page=page, per_page=100)
        block_list_response: GetBlockListActionResponse = parse_get_block_list_response(
            self.execute_request(
                prepare_get_block_list_endpoint(
                    block_list_request.dict(exclude_none=True, by_alias=True)
                )
            )
        )
        nb_pages = block_list_response.pages_count
        if page >= nb_pages:
            return block_list_response.items
        page += 1
        while page <= nb_pages:
            block_list_request.page = page
            block_list_response = parse_get_block_list_response(
                self.execute_request(
                    prepare_get_block_list_endpoint(
                        block_list_request.dict(exclude_none=True, by_alias=True)
                    )
                )
            )
            existing_indicators.extend(block_list_response.items)
            page += 1
        return existing_indicators

    def get_valid_rules(self, stix_objects) -> Dict[str, list]:
        seen_values = defaultdict(list)
        results = {"valid": [], "revoked": []}
        for object in stix_objects:
            # Extract value and type from pattern
            self.log(message=f"object in stix_objects {str(object)}", level="debug")
            indicators = stix_to_indicators(
                stix_object=object, supported_types_map=self.SUPPORTED_TYPES_MAP
            )
            for indicator in indicators:
                ioc_value = indicator["value"]
                ioc_type = indicator["type"]
                ioc_path = indicator.get("path", [])
                result = self.indicator_to_rule(
                    type=ioc_type, value=ioc_value, path=ioc_path
                )

                if result is None:
                    continue

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

    def remove_existing_rules_to_add(
        self, existing_rules: list[ItemsModel], fetch_rules: list[RuleModel]
    ) -> list[RuleModel]:
        existing_rules = self.itemsModelList_to_rules(existing_rules)
        return [rule for rule in fetch_rules if rule not in existing_rules]

    def remove_non_existing_rules_to_revoke(
        self, existing_rules_items: list[ItemsModel], fetch_rules: list[RuleModel]
    ) -> list[ItemsModel]:
        rules = []
        existing_rules = self.itemsModelList_to_rules(existing_rules_items)
        for i in range(len(existing_rules)):
            existing_rule = existing_rules[i]
            if existing_rule in fetch_rules:
                rules.append(existing_rules_items[i])
        return rules

    def remove_revoked_rules(self, rules: list[ItemsModel]):
        """
        Remove revoked rules from the list of rules.
        """
        if ids := [rule.id for rule in rules]:
            remove_request = RemoveBlockActionRequest(ids=ids)
            self.execute_request(
                prepare_remove_block_endpoint(
                    remove_request.dict(exclude_none=True, by_alias=True)
                )
            )

        return

    def add_rules(self, rules: list[RuleModel]):
        """
        Add rules to the block list.
        """
        add_hashes: list[RuleModel] = []
        add_connections: list[RuleModel] = []
        for rule in rules:
            if isinstance(rule.details, HashModel):
                add_hashes.append(rule)
            elif isinstance(rule.details, ConnectionModel):
                add_connections.append(rule)

        if len(add_hashes) > 0:
            # Call the API to add hashes
            args = BlockListModel(type="hash", rules=add_hashes)
            self.execute_request(
                prepare_push_block_endpoint(args.dict(exclude_none=True, by_alias=True))
            )

        if len(add_connections) > 0:
            # Call the API to add connections
            args = BlockListModel(type="connection", rules=add_connections)
            self.execute_request(
                prepare_push_block_endpoint(args.dict(exclude_none=True, by_alias=True))
            )

        return

    def run(self, arguments: dict) -> dict:
        stix_objects = self.json_argument("stix_objects", arguments)

        if stix_objects is None or len(stix_objects) == 0:
            self.log("Received stix_objects were empty")
            return {"result": True}

        existing_rules = self.get_existing_rules()

        fetch_rules = self.get_valid_rules(stix_objects)
        if len(fetch_rules["valid"]) == 0 and len(fetch_rules["revoked"]) == 0:
            self.log("Received indicators were not valid and/or not supported")
            return

        rules_to_add = self.remove_existing_rules_to_add(
            existing_rules, fetch_rules["valid"]
        )
        rules_to_revoke = self.remove_non_existing_rules_to_revoke(
            existing_rules, fetch_rules["revoked"]
        )

        if len(rules_to_add) == 0 and len(rules_to_revoke) == 0:
            self.log("No new indicators to add or revoke")
            return {"result": True}

        if len(rules_to_revoke) > 0:
            self.remove_revoked_rules(rules_to_revoke)

        if len(rules_to_add) > 0:
            self.add_rules(rules_to_add)

        return {"result": True}
