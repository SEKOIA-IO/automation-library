from typing import Any
from pydantic.v1 import BaseModel
from sekoia_automation.action import Action
import re

from xsiam.helpers import iso8601_to_timestamp

TYPE_MAPPING = {
    "file": "HASH",
    "filename": "FILENAME",
    "directory": "PATH",
    "domain-name": "DOMAIN_NAME",
    "ipv4-addr": "IP",
    "ipv6-addr": "IP",
}

HIGH_KILL_CHAIN_PHASES = ["exploitation", "installation", "command-and-control", "actions-on-objectives"]


class ActionArguments(BaseModel):
    stix_objects: list[dict] | None  # List of Stix objects to convert
    stix_objects_path: str | None  # Path to the STIX objects file


class STIXToXSIAMAction(Action):
    def run(self, arguments: ActionArguments) -> Any:
        """
        Convert STIX objects to XSIAM format.
        """
        xsiam_objects = []

        for stix_obj in self.json_argument("stix_objects", arguments.dict()):
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
            "class": stix_obj.get("id", "N/A"),
            "validate": True,
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
        Convert the confidence from STIX to XSIAM severity format.
        """
        confidence = stix_obj.get("confidence", 0)
        kill_chain_phases_name = [phase["phase_name"] for phase in stix_obj.get("kill_chain_phases", [])]

        if (
            confidence >= 80
            and confidence <= 100
            and any(phase_name in HIGH_KILL_CHAIN_PHASES for phase_name in kill_chain_phases_name)
        ):
            return "HIGH"
        elif confidence >= 39:
            return "MEDIUM"
        else:
            return "LOW"

    def _get_comment(self, stix_obj: dict) -> str:
        return f"Valid from {stix_obj.get('valid_from', 'N/A')} AND STIX Pattern: {stix_obj.get('pattern', 'N/A')}"

    def _get_reputation(self) -> str:
        return "BAD"

    def _get_reliability(self, stix_obj: dict) -> str:
        """
        Convert the confidence from STIX to XSIAM format.
        """
        if "confidence" not in stix_obj:
            return "F"

        confidence = stix_obj["confidence"]
        if confidence >= 80:
            return "A"
        elif confidence >= 60:
            return "B"
        elif confidence >= 40:
            return "C"
        elif confidence >= 20:
            return "D"
        else:
            return "E"

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
