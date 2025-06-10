from typing import Any
from pydantic.v1 import BaseModel
from sekoia_automation.action import Action
import re

from xsiam.helpers import iso8601_to_timestamp

TYPE_MAPPING: dict[str, str] = {
    "file": "HASH",
    "filename": "FILENAME",
    "directory": "PATH",
    "domain-name": "DOMAIN_NAME",
    "ipv4-addr": "IP",
    "ipv6-addr": "IP",
}
HIGH_KILL_CHAIN_PHASES: list[str] = ["exploitation", "installation", "command-and-control", "actions-on-objectives"]

DEFAULT_RELIABILITY_MAPPING: list[dict[str, str]] = [
    {
        "confidence": "80",
        "reliability": "A",
    },
    {
        "confidence": "60",
        "reliability": "B",
    },
    {
        "confidence": "40",
        "reliability": "C",
    },
    {
        "confidence": "20",
        "reliability": "D",
    },
    {
        "confidence": "0",
        "reliability": "E",
    },
]
DEFAULT_SEVERITY_MAPPING: list[dict[str, str | list[str]]] = [
    {
        "confidence": "80",
        "kill_chain_phases": HIGH_KILL_CHAIN_PHASES,
        "severity": "HIGH",
    },
    {
        "confidence": "40",
        "kill_chain_phases": [],
        "severity": "MEDIUM",
    },
    {
        "confidence": "0",
        "kill_chain_phases": [],
        "severity": "LOW",
    },
]
# Default mapping of STIX reputation to XSIAM reputation
DEFAULT_COMMENT = "Valid from {valid_from} AND STIX Pattern: {pattern}"  # Default comment for XSIAM objects
DEFAULT_CLASS_OVERRIDE = "{id}"  # Default class override for XSIAM objects


class ActionArguments(BaseModel):
    stix_objects: list[dict] | None  # List of Stix objects to convert
    stix_objects_path: str | None  # Path to the STIX objects file
    reliability_mapping: list[dict[str, str]] | None = (
        DEFAULT_RELIABILITY_MAPPING  # Mapping of STIX reputation to XSIAM reputation
    )
    severity_mapping: list[dict[str, str | list[str]]] | None = (
        DEFAULT_SEVERITY_MAPPING  # Mapping of STIX confidence and kill chain phase to XSIAM severity
    )
    comment: str | None = DEFAULT_COMMENT  # Comment to add to the XSIAM object
    class_override: str | None = DEFAULT_CLASS_OVERRIDE  # Override class for the XSIAM object


class STIXToXSIAMAction(Action):
    def run(self, arguments: ActionArguments) -> Any:
        """
        Convert STIX objects to XSIAM format.
        """
        args = arguments.dict()
        self.reliability_mapping = args.get("reliability_mapping", DEFAULT_RELIABILITY_MAPPING)
        self.severity_mapping = args.get("severity_mapping", DEFAULT_SEVERITY_MAPPING)
        self.comment = args.get("comment", DEFAULT_COMMENT)
        self.class_override = args.get("class_override", DEFAULT_CLASS_OVERRIDE)

        xsiam_objects = []

        for stix_obj in self.json_argument("stix_objects", args):
            stix_type = self._get_type(stix_obj)
            if stix_type == "UNKNOWN":
                continue

            patterns = self._get_patterns(stix_obj)

            for pattern in patterns:
                xsiam_obj = self._create_xsiam_object(pattern, stix_type, stix_obj)
                xsiam_objects.append(xsiam_obj)

        return {"data": xsiam_objects}

    def _create_xsiam_object(self, pattern: str, stix_type: str, stix_obj: dict) -> dict:
        return {
            "indicator": pattern,
            "type": stix_type,
            "severity": self._get_severity(stix_obj),
            "expiration_date": iso8601_to_timestamp(stix_obj.get("valid_until", "1970-01-01T00:00:00Z")),
            "comment": self._get_comment(stix_obj),
            "reputation": self._get_reputation(),
            "reliability": self._get_reliability(stix_obj),
            "vendors": self._get_vendors(stix_obj),
            "class": self._get_class(stix_obj),
        }

    def _get_patterns(self, stix_obj: dict) -> list[str]:
        """
        Convert the pattern from STIX to XSIAM format.
        """
        pattern = stix_obj.get("pattern")
        if pattern is None:
            return []

        if hashes := re.findall(
            r"file:hashes\.'?(?:MD5|SHA-256)'?\s?=\s?'(?P<value>.*?)'", pattern, flags=re.DOTALL | re.MULTILINE
        ):
            return hashes
        else:
            return re.findall(r":value\s?=\s?'(?P<value>.+?)'", pattern, flags=re.DOTALL | re.MULTILINE)

    def _get_type(self, stix_obj: dict) -> str:
        """
        Convert the x_ic_observable_types from STIX to XSIAM type format.
        """
        observable_type = stix_obj.get("x_ic_observable_types", [])
        if len(observable_type) == 1:
            return TYPE_MAPPING.get(observable_type[0], "UNKNOWN")

        return "UNKNOWN"

    def _get_severity(self, stix_obj: dict) -> str:
        """
        Convert the confidence and kill chain phase from STIX to XSIAM severity format.
        """
        confidence = stix_obj.get("confidence", 0)
        kill_chain_phases_name = [phase["phase_name"] for phase in stix_obj.get("kill_chain_phases", [])]

        for mapping in self.severity_mapping:
            if "kill_chain_phases" not in mapping:
                if confidence >= int(mapping["confidence"]):
                    return mapping["severity"]
            if (
                confidence >= int(mapping["confidence"])
                and not mapping["kill_chain_phases"]
                or any(phase in kill_chain_phases_name for phase in mapping["kill_chain_phases"])
            ):
                return mapping["severity"]

        return "LOW"  # Default to lowest severity if not found

    def _get_comment(self, stix_obj: dict) -> str:
        return self._format_string_from_stix(stix_obj, self.comment)

    def _get_class(self, stix_obj: dict) -> str:
        return self._format_string_from_stix(stix_obj, self.class_override)

    def _format_string_from_stix(self, stix_obj: dict, string: str) -> str:
        """
        Format the comment string with properties from the STIX object.
        """
        properties = re.findall(r"{(.*?)}", string, flags=re.DOTALL)
        properties_dict = {}

        for property in properties:
            properties_dict[property] = stix_obj.get(property, "N/A")

        return string.format(**properties_dict)

    def _get_reputation(self) -> str:
        return "BAD"

    def _get_reliability(self, stix_obj: dict) -> str:
        """
        Convert the confidence from STIX to XSIAM format.
        """
        if "confidence" not in stix_obj:
            return "F"

        confidence = stix_obj["confidence"]
        for mapping in self.reliability_mapping:
            if confidence >= int(mapping["confidence"]):
                return mapping["reliability"]

        return "F"  # Default to lowest reliability if not found

    def _get_vendors(self, stix_obj: dict) -> list[dict]:
        """
        Convert the x_inthreat_sources from STIX to XSIAM vendor format.
        """
        if "x_inthreat_sources" not in stix_obj:
            return []

        vendors = []
        sources = stix_obj["x_inthreat_sources"]

        for source in sources:
            vendors.append(
                {
                    "vendor_name": source.get("name", "N/A"),
                    "reliability": self._get_reliability(source),
                    "reputation": self._get_reputation(),
                }
            )

        return vendors
