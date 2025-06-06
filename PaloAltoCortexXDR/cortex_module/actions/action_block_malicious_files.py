from typing import Any

import six
from pydantic.main import BaseModel
from stix2patterns.pattern import Pattern

from cortex_module.actions import PaloAltoCortexXDRAction


def is_a_supported_stix_indicator(stix_object: dict[str, Any]) -> bool:
    # Check if indicator is STIX
    pattern_type = stix_object.get("pattern_type")
    if pattern_type is not None and pattern_type != "stix":
        return False
    else:
        return True


def transform_stix(
    stix_object: dict[str, Any], supported_types_map: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    """
    Extract indicators type and value from the STIX pattern.

    supported_types_map is used to define the mapping from STIX pattern
    to the different IOCs types supported by Crowdstrike Falcon.
    "stix_root_key": {"stix_sub_key": "target_type"}
    Example with ipv4:
    Mapping with "ipv4-addr": {"value": "ipv4"} for IOC "[ipv4-addr:value = 'X.X.X.X']"
    """
    if not is_a_supported_stix_indicator(stix_object):
        return []

    parsed_pattern = Pattern(stix_object["pattern"])
    results = []
    for observable_type, comparisons in six.iteritems(parsed_pattern.inspect().comparisons):
        if observable_type not in supported_types_map:
            continue

        for path, operator, value in comparisons:
            try:
                path = ".".join(path)
            except TypeError:
                # This happens when the pattern contains '*', which is unsupported
                continue

            if path not in supported_types_map[observable_type]:
                continue

            if operator != "=":
                continue

            # Get ioc type and value
            ioc_type = supported_types_map[observable_type][path]
            ioc_value = value.strip("'")

            results.append({"type": ioc_type, "value": ioc_value})

    return results


class BlockMaliciousFilesArguments(BaseModel):
    """
    Arguments for the block malicious files action.
    """

    stix_objects: list[dict[str, Any]] | None = None  # only for tests purposes
    stix_objects_path: str
    comment: str
    incident_id: int


class BlockMaliciousFilesAction(PaloAltoCortexXDRAction):
    """
    This action is used to block malicious files.
    """

    request_uri = "public_api/v1/hash_exceptions/blocklist"

    supported_stix_types = {
        "file": {"hashes.MD5": "md5", "hashes.SHA-256": "sha256"},
    }

    def request_payload(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Build the request payload for the action.

        Example of payload:
        {
          "request_data": {
            "hash_list": [
              "<list values>"
            ],
            "comment": "<string>",
            "incident_id": <int>
          }
        }

        Args:
            arguments: The arguments passed to the action.

        Returns:
            dict[str, Any]: The request payload.
        """
        model = BlockMaliciousFilesArguments(**arguments)

        # If `name`_path is inside arguments, returns the content of the file
        stix_objects: list[dict[str, Any]] = self.json_argument("stix_objects", model.dict())

        if stix_objects is None or len(stix_objects) == 0:
            self.log("Received stix_objects were empty")

        hashes = []
        for value in stix_objects:
            # Extract value and type from pattern
            self.log(message=f"object in stix_objects {str(value)}", level="debug")
            stix_result = transform_stix(stix_object=value, supported_types_map=self.supported_stix_types)

            for ioc in stix_result:
                # Add the hash to the list
                hashes.append(ioc["value"])

        if not hashes:
            raise ValueError("No hashes found in the STIX objects")

        return {
            "request_data": {
                "hash_list": hashes,
                "comment": model.comment,
                "incident_id": model.incident_id,
            }
        }
