import uuid
from datetime import datetime
from typing import Any

from idstools.rule import Rule

from detection_rules.utils import datetime_to_str


class RuleSerializer:
    # Any of this rule options discard the rule
    # because they need the body of the request
    black_list = {
        "http_client_body",
        "file_data",
        "pkt_data",
        "rawbytes",
        "dce_iface",
        "dce_opnum",
        "dce_stub_data",
        "sip_method",
        "sip_stat_code",
        "sip_header",
        "sip_body",
        "gtp_type",
        "gtp_info",
        "gtp_version",
        "http_header",
        "http_raw_header",
        "http_raw_cookie",
        "http_cookie",
        "http_header_names",
        "tls_cert_subject",
        "tls_cert_issuer",
        "tls_cert_serial",
        "tls_cert_fingerprint",
        "tls_cert_expired",
        "tls_cert_valid",
        "tls.subject",
        "tls.issuerdn",
        "tls.fingerprint",
    }

    # We must have at least one of this rule option
    white_list = {
        "uricontent",
        "urilen",
        "http_stat_code",
        "http_stat_msg",
        "http_encode",
        "http_uri",
        "http_raw_uri",
        "http_method",
        "http_request_line",
        "http_user_agent",
        "http_host",
        "http_raw_host",
        "http_accept",
        "http_accept_lang",
        "http_accept_enc",
        "http_referer",
        "http_connection",
        "http_content_type",
        "http_content_len",
        "http_start",
        "http_protocol",
        "tls.version",
        "ssl_version",
        "ssl_state",
        "ssh_proto",
        "ssh_version",
        "dns_query",
    }

    reference_urls = {
        "bugtraq": "http://www.securityfocus.com/bid/",
        "cve": "http://cve.mitre.org/cgi-bin/cvename.cgi?name=",
        "nessus": "http://cgi.nessus.org/plugins/dump.php3?id=",
        "arachnids": "http://www.whitehats.com/info/IDS",
        "mcafee": "http://vil.nai.com/vil/content/v_",
        "osvdb": "http://osvdb.org/show/osvdb/",
        "msb": "http://technet.microsoft.com/en-us/security/bulletin/",
        "url": "http://",
    }

    def __init__(self, rule_type: str, rule_version: str | None):
        self.rule_type = rule_type
        self.rule_version = rule_version

    def to_stix(self, rules: list[Rule]):
        return [self._to_stix(rule) for rule in rules if self.is_valid(rule)]

    def is_valid(self, rule: Rule):
        # Rule is disabled in the file
        if not rule.enabled:
            return False
        has_white_list_name = False
        for option in rule.options:
            if option["name"] in self.black_list:
                # Any name in the blacklist discards the rule
                return False
            if option["name"] in self.white_list:
                # At least one name in the white list is required
                has_white_list_name = True
        return has_white_list_name

    def _to_stix(self, rule: Rule):
        """
        Convert a rule into a STIX object
        """
        rule_dict: dict[str, Any] = {
            "id": f"indicator--{str(uuid.uuid4())}",
            "type": "indicator",
            "name": f"{rule.msg} (sid {rule.sid})",
            "pattern_type": self.rule_type,
            "pattern": str(rule),
            "valid_from": datetime_to_str(datetime.utcnow()),
            "external_references": [],
        }
        if self.rule_version:
            rule_dict["pattern_version"] = self.rule_version

        for reference in rule.references:
            # From doc reference is <id_system>,<ref_id>
            id_system, ref_id = reference.split(",", 1)
            reference_dict = {"source_name": id_system, "external_id": ref_id}
            base_url = self.reference_urls.get(id_system)
            if base_url:
                reference_dict["url"] = f"{base_url}{ref_id}"
            rule_dict["external_references"].append(reference_dict)

        return rule_dict
