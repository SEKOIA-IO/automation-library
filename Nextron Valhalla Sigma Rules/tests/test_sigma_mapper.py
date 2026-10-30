import textwrap

import pytest
import yaml

from nextron_valhalla_sigma_rules_modules.ecs_field_maps import RAW_TO_ECS, RAW_TO_ECS_BY_PRODUCT
from nextron_valhalla_sigma_rules_modules.sigma_mapper import (
    DEFAULT_SEVERITY,
    MARKER_TAG,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    RULE_EFFORT,
    SEVERITY_MAP,
    convert_payload_to_ecs,
    sigma_rule_to_catalog_payload,
)

# ---------------------------------------------------------------------------
# sigma_rule_to_catalog_payload — new structured-body shape
# ---------------------------------------------------------------------------


def _rule_and_parsed(content: str, rule_id: str = "abc-123", filename: str | None = None):
    """Return (rule, parsed) pair for feeding sigma_rule_to_catalog_payload."""
    rule: dict = {"id": rule_id, "content": content}
    if filename is not None:
        rule["filename"] = filename
    parsed = yaml.safe_load(content) or {}
    return rule, parsed


HIGH_RULE_YAML = """\
title: Suspicious process creation
description: Detects a suspicious process being spawned.
level: high
logsource:
  product: windows
detection:
  selection: {EventID: 4688}
  condition: selection
"""


def test_maps_required_fields():
    rule, parsed = _rule_and_parsed(HIGH_RULE_YAML, filename="proc_creation.yml")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)

    assert body["name"] == "Suspicious process creation"
    assert body["type"] == "sigma"
    assert body["description"] == "Detects a suspicious process being spawned."
    assert body["severity"] == 70
    assert body["effort"] == RULE_EFFORT
    # No tactic tag → default alert type (application-compromise).
    assert body["alert_type_uuid"] == "599f4b1a-dd60-43fe-8ee9-07d3c5d00ded"
    assert body["enabled"] is False


def test_payload_carries_logsource_and_detection_only():
    """S11: the payload keeps the Sigma ``logsource`` next to the converted
    ``detection``; other metadata travels in structured fields."""
    rule, parsed = _rule_and_parsed(HIGH_RULE_YAML)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)

    assert body["payload"].startswith("logsource:")
    assert "title:" not in body["payload"]
    assert "description:" not in body["payload"]
    assert "references:" not in body["payload"]
    assert "level:" not in body["payload"]


def test_payload_roundtrips_back_to_logsource_and_detection():
    rule, parsed = _rule_and_parsed(HIGH_RULE_YAML)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)

    reparsed = yaml.safe_load(body["payload"])
    assert list(reparsed) == ["logsource", "detection"]
    assert reparsed["logsource"] == parsed["logsource"]
    assert "condition" in reparsed["detection"]
    assert "selection" in reparsed["detection"]


def test_payload_without_logsource_is_detection_only():
    rule, parsed = _rule_and_parsed("title: t\ndetection: {selection: {a: 1}, condition: selection}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert list(yaml.safe_load(body["payload"])) == ["detection"]


def test_enabled_flag_propagates():
    rule, parsed = _rule_and_parsed(HIGH_RULE_YAML)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=True)
    assert body["enabled"] is True


@pytest.mark.parametrize(
    "level,expected",
    [
        ("informational", 10),
        ("low", 30),
        ("medium", 50),
        ("high", 70),
        ("critical", 90),
    ],
)
def test_severity_mapping_per_level(level, expected):
    rule, parsed = _rule_and_parsed(
        f"title: t\nlevel: {level}\ndetection: {{selection: {{a: 1}}, condition: selection}}\n"
    )
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["severity"] == expected


def test_severity_map_matches_public_constant():
    assert SEVERITY_MAP == {
        "informational": 10,
        "low": 30,
        "medium": 50,
        "high": 70,
        "critical": 90,
    }


def test_severity_falls_back_to_default_when_level_missing():
    rule, parsed = _rule_and_parsed("title: no-level\ndetection: {}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["severity"] == DEFAULT_SEVERITY == 0


@pytest.mark.parametrize("status", ["stable", "test", "experimental", "STABLE", None])
def test_effort_is_fixed_whatever_the_status(status):
    """S17: ``effort`` is the expected analysis effort, not Sigma maturity."""
    status_line = f"status: {status}\n" if status else ""
    rule, parsed = _rule_and_parsed(f"title: t\n{status_line}detection: {{}}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["effort"] == RULE_EFFORT


@pytest.mark.parametrize("status", ["stable", "test", "experimental", "STABLE"])
def test_sigma_status_becomes_a_tag(status):
    rule, parsed = _rule_and_parsed(f"title: t\nstatus: {status}\ndetection: {{}}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert f"status-{status.lower()}" in body["tags"]


def test_no_status_tag_when_status_missing():
    rule, parsed = _rule_and_parsed("title: t\ndetection: {}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert not any(t.startswith("status-") for t in body["tags"])


def test_title_falls_back_to_filename_when_yaml_lacks_title():
    rule, parsed = _rule_and_parsed(
        "description: no title here\nlevel: medium\ndetection: {}\n",
        filename="fallback_name.yml",
    )
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["name"] == "fallback_name.yml"


def test_uses_top_level_level_field_when_yaml_lacks_one():
    """If the parsed dict lacks `level`, the rule's top-level `level` is used."""
    rule = {"id": "x", "filename": "n.yml", "level": "critical"}
    parsed = {"title": "t"}
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["severity"] == 90


def test_name_is_truncated_when_over_sekoia_limit():
    long_title = (
        "CVE-2023-1389 Potential Exploitation Attempt - Unauthenticated Command Injection In TP-Link Archer AX21"
    )
    assert len(long_title) > MAX_NAME_LENGTH
    rule, parsed = _rule_and_parsed(f"title: {long_title}\ndetection: {{}}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert len(body["name"]) <= MAX_NAME_LENGTH
    assert body["name"].endswith("…")
    assert body["name"].startswith("CVE-2023-1389")


def test_name_at_exact_limit_is_untouched():
    title = "x" * MAX_NAME_LENGTH
    rule, parsed = _rule_and_parsed(f"title: {title}\ndetection: {{}}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["name"] == title
    assert not body["name"].endswith("…")


def test_description_is_truncated_when_over_sekoia_limit():
    long_desc = "x" * (MAX_DESCRIPTION_LENGTH + 500)
    rule, parsed = _rule_and_parsed(f"title: t\ndescription: {long_desc}\ndetection: {{}}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert len(body["description"]) <= MAX_DESCRIPTION_LENGTH
    assert body["description"].endswith("…")


def test_description_at_exact_limit_is_untouched():
    desc = "y" * MAX_DESCRIPTION_LENGTH
    rule, parsed = _rule_and_parsed(f"title: t\ndescription: {desc}\ndetection: {{}}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["description"] == desc
    assert not body["description"].endswith("…")


def test_short_name_untouched():
    rule, parsed = _rule_and_parsed("title: Short Name\ndetection: {}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["name"] == "Short Name"


# ---------------------------------------------------------------------------
# Optional Sekoia fields — present per-rule only when the Sigma source has them.
# ---------------------------------------------------------------------------


def test_community_uuid_is_never_shipped():
    """Setting community_uuid triggers Sekoia's AU202 scope check when
    combined with other metadata fields, and Sekoia overrides our value
    with its own default anyway. We omit it entirely."""
    rule, parsed = _rule_and_parsed("title: t\ndetection: {}\n", rule_id="valhalla-xyz")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert "community_uuid" not in body


def test_tags_pass_through_and_marker_is_appended():
    yaml_body = "title: t\ntags:\n  - attack.credential-access\n  - cve.2023-1389\ndetection: {}\n"
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["tags"] == [
        "attack.credential-access",
        "cve.2023-1389",
        MARKER_TAG,
        "uuid-abc-123",
    ]


def test_marker_tag_is_added_when_source_has_no_tags():
    rule, parsed = _rule_and_parsed("title: t\ndetection: {}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["tags"] == [MARKER_TAG, "uuid-abc-123"]


def test_uuid_tag_carries_valhalla_id():
    """Every rule we POST/PUT carries a ``uuid-<valhalla_id>`` tag so the
    sync trigger can rebuild the id-map from the Sekoia catalog when its
    local file is empty (fresh playbook, recreated trigger)."""
    rule, parsed = _rule_and_parsed("title: t\ndetection: {}\n", rule_id="feed-uuid-xyz")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert "uuid-feed-uuid-xyz" in body["tags"]


def test_uuid_tag_omitted_when_rule_has_no_id():
    """A feed entry missing ``id`` can still be partially rendered (name
    falls back to filename) but no uuid tag is added — we have nothing
    to key it on."""
    rule = {"content": "title: t\ndetection: {}\n", "filename": "x.yml"}
    parsed = {"title": "t", "detection": {}}
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["tags"] == [MARKER_TAG]


def test_uuid_tag_is_not_duplicated():
    yaml_body = "title: t\ntags:\n  - uuid-abc-123\ndetection: {}\n"
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["tags"].count("uuid-abc-123") == 1


def test_marker_tag_is_not_duplicated():
    yaml_body = f"title: t\ntags:\n  - {MARKER_TAG}\n  - attack.t1059\ndetection: {{}}\n"
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["tags"].count(MARKER_TAG) == 1


def test_datasources_not_shipped_even_when_logsource_present():
    # Sekoia's `datasources` is a list of tenant-registered data-source UUIDs,
    # not the Sigma logsource dict. We can't derive UUIDs from `{product,
    # category}`, so the field is intentionally omitted.
    yaml_body = "title: t\nlogsource:\n  product: windows\n  category: process_creation\ndetection: {}\n"
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert "datasources" not in body


def test_related_object_refs_is_never_shipped():
    """Sigma's `related` list carries Sigma-world UUIDs that don't map to
    anything in Sekoia's tenant catalog — shipping them as
    `related_object_refs` would just add dangling references. Field is
    intentionally omitted."""
    yaml_body = (
        "title: t\nrelated:\n  - id: 8cf4da11-0d3b-4a4f-9f5f-abcdef012345\n    type: obsoletes\ndetection: {}\n"
    )
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert "related_object_refs" not in body


def test_false_positives_list_is_joined_with_newlines():
    yaml_body = "title: t\nfalsepositives:\n  - Legit scanners\n  - IT admin scripts\n  - Backup jobs\ndetection: {}\n"
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["false_positives"] == "Legit scanners\nIT admin scripts\nBackup jobs"


def test_false_positives_string_kept_as_string():
    yaml_body = "title: t\nfalsepositives: 'Legit scanners'\ndetection: {}\n"
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["false_positives"] == "Legit scanners"


def test_false_positives_omitted_when_absent():
    rule, parsed = _rule_and_parsed("title: t\ndetection: {}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert "false_positives" not in body


def test_all_optional_fields_together():
    yaml_body = (
        "title: Full Rule\n"
        "description: All fields.\n"
        "level: high\n"
        "status: stable\n"
        "tags: [attack.t1059]\n"
        "logsource: {product: windows, category: process_creation}\n"
        "falsepositives: [Legit tool]\n"
        "related: [{id: 00000000-0000-0000-0000-000000000000, type: derived}]\n"
        "detection: {selection: {a: 1}, condition: selection}\n"
    )
    rule, parsed = _rule_and_parsed(yaml_body, rule_id="valhalla-1")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=True)
    assert set(body.keys()) == {
        "name",
        "type",
        "description",
        "payload",
        "severity",
        "effort",
        "alert_type_uuid",
        "enabled",
        "tags",
        "false_positives",
    }
    assert body["severity"] == 70
    assert body["effort"] == RULE_EFFORT
    assert "status-stable" in body["tags"]
    assert body["enabled"] is True
    assert "datasources" not in body
    assert "community_uuid" not in body
    assert "related_object_refs" not in body


# ---------------------------------------------------------------------------
# derive_alert_type_uuid — Sigma tag → Sekoia alert_type_uuid
# ---------------------------------------------------------------------------


from nextron_valhalla_sigma_rules_modules.sigma_mapper import (  # noqa: E402
    DEFAULT_ALERT_UUID,
    TAG_ALERT_UUID_MAP,
    derive_alert_type_uuid,
)


@pytest.mark.parametrize("tag,expected_uuid", list(TAG_ALERT_UUID_MAP))
def test_each_priority_tag_maps_to_expected_uuid(tag, expected_uuid):
    assert derive_alert_type_uuid([tag]) == expected_uuid


def test_no_tactic_tag_returns_default():
    assert derive_alert_type_uuid([]) == DEFAULT_ALERT_UUID
    assert derive_alert_type_uuid(["attack.t1059"]) == DEFAULT_ALERT_UUID
    assert derive_alert_type_uuid(["cve.2023-1389"]) == DEFAULT_ALERT_UUID
    assert derive_alert_type_uuid(["stp.5.1"]) == DEFAULT_ALERT_UUID


def test_priority_tie_break_higher_wins():
    # Exfiltration wins over persistence.
    exfiltration_uuid = "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"
    backdoor_uuid = "5928d144-2038-4a87-b996-b3585a9a1a41"
    assert derive_alert_type_uuid(["attack.persistence", "attack.exfiltration"]) == exfiltration_uuid
    # Order in the tag list must not matter — priority list is authoritative.
    assert derive_alert_type_uuid(["attack.exfiltration", "attack.persistence"]) == exfiltration_uuid
    # Sanity: backdoor is what persistence alone yields.
    assert derive_alert_type_uuid(["attack.persistence"]) == backdoor_uuid


def test_case_insensitive_tag_matching():
    exfiltration_uuid = "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"
    assert derive_alert_type_uuid(["ATTACK.EXFILTRATION"]) == exfiltration_uuid


def test_non_string_tag_entries_are_ignored():
    # Defensive: tags list occasionally contains non-strings from odd YAML.
    exfiltration_uuid = "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"
    assert derive_alert_type_uuid([None, 123, "attack.exfiltration"]) == exfiltration_uuid


def test_marker_tag_alone_does_not_override_default():
    # The marker tag must not accidentally match any priority-list entry.
    from nextron_valhalla_sigma_rules_modules.sigma_mapper import MARKER_TAG

    assert derive_alert_type_uuid([MARKER_TAG]) == DEFAULT_ALERT_UUID


def test_body_alert_type_uuid_derived_from_tags():
    """End-to-end: a rule tagged attack.exfiltration ends up with the
    exfiltration alert_type_uuid in the POSTed body."""
    yaml_body = "title: t\ntags: [attack.exfiltration, attack.t1041]\ndetection: {}\n"
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["alert_type_uuid"] == "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"


# ---------------------------------------------------------------------------
# convert_payload_to_ecs — Stage 1 conversion
# ---------------------------------------------------------------------------


def _single_field_rule(field: str, value: str = "'foo'", product: str | None = None) -> str:
    logsource = f"logsource:\n  product: {product}\n" if product else ""
    return f"title: T\n{logsource}detection:\n  selection:\n    {field}: {value}\n  condition: selection\n"


@pytest.mark.parametrize(
    "raw,ecs",
    [
        # SigmaHQ Windows pipeline (source of truth)
        ("Image", "process.executable"),  # .caseless stripped
        ("CommandLine", "process.command_line"),
        ("ParentImage", "process.parent.executable"),  # .caseless stripped
        ("ParentCommandLine", "process.parent.command_line"),
        ("EventID", "event.code"),
        ("TargetFilename", "file.path"),
        ("ScriptBlockText", "powershell.file.script_block_text"),
        ("DestinationIp", "destination.ip"),
        ("QueryName", "dns.question.name"),
        ("User", "user.name"),
        ("Signed", "file.code_signature.signed"),  # SigmaHQ prefixes with `file.`
        ("SignatureStatus", "file.code_signature.status"),
        ("TargetDomainName", "user.target.domain"),
        # Web / proxy W3C ELF fields (Zeek pipeline)
        ("cs-method", "http.request.method"),
        ("cs-referer", "http.request.referrer"),
        ("cs-uri-query", "url.query"),
        ("cs-uri-stem", "url.original"),  # Zeek target (was url.path)
        ("cs-uri", "url.original"),
        ("sc-status", "http.response.status_code"),
        # Cloud (custom mappings, SigmaHQ doesn't cover)
        ("eventName", "event.action"),
        ("eventSource", "event.provider"),
        ("operationName", "event.action"),
        ("errorCode", "event.code"),
        ("riskEventType", "azuread.properties.riskEventType"),
        ("AuthenticationRequirement", "azuread.properties.authenticationRequirement"),
        # Linux auditd
        ("SYSCALL", "auditd.data.syscall"),
        ("a0", "auditd.data.a0"),
        ("a1", "auditd.data.a1"),
        ("exe", "process.executable"),
        ("cfgpath", "auditd.data.cfgpath"),
        # Custom W3C ELF variants
        ("userAgent", "user_agent.original"),
        ("cs-user-agent", "user_agent.original"),
        ("user_agent", "user_agent.original"),
        # macOS (SigningID unique to pySigma macos pipeline)
        ("SigningID", "process.code_signature.signing_id"),
        ("PtraceRequest", "ptrace.request"),
        # Zeek network
        ("dst_ip", "destination.ip"),
        ("src_ip", "source.ip"),
        # Kubernetes (verified against Sekoia's kubernetes-audit-log parser)
        ("verb", "event.action"),
        ("apiGroup", "kubernetes.api.group"),
        ("objectRef.name", "kubernetes.object.name"),
        ("objectRef.namespace", "kubernetes.namespace"),
        ("objectRef.resource", "kubernetes.resource"),
        ("objectRef.apiGroup", "kubernetes.api.group"),
        ("objectRef.subresource", "kubernetes.subresource"),
        # Zeek file/TLS fingerprint fields (verified against Sekoia's
        # Corelight parser — flat file.hash.*/file.mime_type/tls.*)
        ("md5", "file.hash.md5"),
        ("sha1", "file.hash.sha1"),
        ("sha256", "file.hash.sha256"),
        ("mime_type", "file.mime_type"),
        ("ja3", "tls.client.ja3"),
        ("ja3s", "tls.server.ja3s"),
    ],
)
def test_tier1_field_maps_correctly(raw, ecs):
    payload = _single_field_rule(raw)
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted is not None

    parsed = converted
    selection = parsed["detection"]["selection"]
    assert ecs in selection
    assert raw not in selection


def test_modifier_is_preserved():
    payload = _single_field_rule("CommandLine|contains", "'malware.exe'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    assert "process.command_line|contains" in parsed["detection"]["selection"]


def test_multiple_modifiers_are_preserved():
    payload = _single_field_rule("CommandLine|contains|base64offset", "'foo'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    assert "process.command_line|contains|base64offset" in parsed["detection"]["selection"]


def test_hyphenated_field_with_modifier_maps_correctly():
    """Regression: W3C-ELF fields like `cs-uri-query` must split correctly
    even when followed by pipe-separated modifiers."""
    payload = _single_field_rule("cs-uri-query|contains", "'exploit'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    assert "url.query|contains" in parsed["detection"]["selection"]


def test_hyphenated_field_with_multiple_modifiers():
    payload = _single_field_rule("cs-method|contains|all", "'PROPFIND'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    assert "http.request.method|contains|all" in parsed["detection"]["selection"]


def test_unmapped_field_returns_none_and_lists_field():
    payload = _single_field_rule("NonExistentField", "'foo'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["NonExistentField"]


def test_unmapped_fields_are_deduplicated_and_sorted():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection_a:
            BField: x
            AField: x
          selection_b:
            AField: y
          condition: selection_a
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["AField", "BField"]


def test_mixed_mapped_and_unmapped_returns_all_unmapped_fields():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            CommandLine: 'foo'
            NonExistent: 'bar'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["NonExistent"]


def test_nested_selection_blocks_all_get_walked():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection_1:
            Image|endswith: '\\a.exe'
          selection_2:
            CommandLine|contains: 'foo'
          filter_x:
            ParentImage|endswith: '\\parent.exe'
          condition: 1 of selection_* and not filter_x
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    det = parsed["detection"]
    assert "process.executable|endswith" in det["selection_1"]
    assert "process.command_line|contains" in det["selection_2"]
    assert "process.parent.executable|endswith" in det["filter_x"]
    assert det["condition"] == "1 of selection_* and not filter_x"


def test_list_of_dict_selection_is_walked():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            - Image|endswith: '\\a.exe'
            - Image|endswith: '\\b.exe'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    assert all("process.executable|endswith" in item for item in parsed["detection"]["selection"])


def test_multi_value_lists_are_preserved():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Image|endswith:
              - '\\curl.exe'
              - '\\wget.exe'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    values = parsed["detection"]["selection"]["process.executable|endswith"]
    assert values == ["\\curl.exe", "\\wget.exe"]


def test_non_detection_content_is_untouched():
    payload = textwrap.dedent(
        """\
        title: Something with CommandLine in the title
        description: |
          Detects processes that reference Image in their description text.
        references:
          - https://example.com/EventID/foo
        detection:
          selection:
            CommandLine: 'foo'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    assert parsed["title"] == "Something with CommandLine in the title"
    assert "Image" in parsed["description"]
    assert "EventID" in parsed["references"][0]


def test_condition_key_is_never_walked_as_field():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            CommandLine: 'foo'
          condition: selection and not something
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    assert parsed["detection"]["condition"] == "selection and not something"


def test_dotted_field_names_are_treated_as_single_field():
    """A dotted field like `something.deeply.nested` is one field, not three."""
    payload = _single_field_rule("custom.unmapped.field", "'foo'")
    converted, unmapped = convert_payload_to_ecs(payload)
    # Not in the map; should be reported as one unmapped field, not split.
    assert converted is None
    assert unmapped == ["custom.unmapped.field"]


def test_malformed_yaml_returns_parse_error_marker():
    converted, unmapped = convert_payload_to_ecs("[unclosed flow sequence")
    assert converted is None
    assert unmapped == ["<yaml-parse-error>"]


def test_missing_detection_block_returns_marker():
    payload = "title: T\nlevel: medium\n"
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["<no-detection>"]


def test_custom_mapping_overrides_default():
    payload = _single_field_rule("Foo|contains", "'bar'")
    converted, unmapped = convert_payload_to_ecs(payload, mapping={"Foo": "custom.ecs.field"})
    assert unmapped == []
    parsed = converted
    assert "custom.ecs.field|contains" in parsed["detection"]["selection"]


def test_windows_process_access_keeps_source_and_target_apart():
    """C1: Sekoia's parser keeps the access *source* in ``process.*`` and
    the target under ``action.properties.*`` (Sysmon 10 fixture)."""
    win = RAW_TO_ECS_BY_PRODUCT["windows"]
    assert win["SourceImage"] == "process.executable"
    assert win["Image"] == "process.executable"
    assert win["TargetImage"] == "action.properties.TargetImage"
    assert win["TargetProcessId"] == "action.properties.TargetProcessId"
    assert win["TargetProcessGUID"] == "action.properties.TargetProcessGUID"


def test_lsass_access_rule_keeps_both_conditions():
    payload = textwrap.dedent(
        """\
        title: T
        logsource:
          product: windows
          category: process_access
        detection:
          selection:
            SourceImage|endswith: '\\rundll32.exe'
            TargetImage|endswith: '\\lsass.exe'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == {
        "process.executable|endswith": "\\rundll32.exe",
        "action.properties.TargetImage|endswith": "\\lsass.exe",
    }


@pytest.mark.parametrize("a,b", [("ProcessId", "SourceProcessId"), ("User", "AccountName")])
def test_colliding_fields_mark_rule_unmapped(a, b):
    """C1: two source keys resolving to the same ECS key would silently drop
    a condition — the rule is reported unmapped instead."""
    payload = (
        "title: T\nlogsource:\n  product: windows\n  category: process_access\n"
        f"detection:\n  selection:\n    {a}: x\n    {b}: y\n  condition: selection\n"
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert len(unmapped) == 1
    assert unmapped[0].startswith("<collision:")


def test_url_fields_collide_in_one_selection():
    payload = _single_field_rule("c-uri", "'/a'\n    cs-uri-stem: '/b'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["<collision:url.original>"]


# ---------------------------------------------------------------------------
# Provenance — SigmaHQ pipelines vs. Custom
# ---------------------------------------------------------------------------


def test_sigmahq_pipelines_load_without_caseless_suffix():
    """Sekoia's ECS schema doesn't expose `.caseless` sub-fields; the merge
    strips the suffix. Confirm no runtime target still carries it."""
    for target in RAW_TO_ECS.values():
        assert not target.endswith(".caseless"), target


def test_product_picks_its_own_field_map():
    """S9: macOS rules use the macOS map (``ProcessName`` → ``process.name``),
    not the Windows targets."""
    mac = RAW_TO_ECS_BY_PRODUCT["macos"]
    win = RAW_TO_ECS_BY_PRODUCT["windows"]
    assert mac["ProcessName"] == "process.name"
    assert mac["FileName"] == "file.name"
    assert win["ProcessName"] == "process.executable"
    assert win["FileName"] == "file.path"

    payload = textwrap.dedent(
        """\
        title: T
        logsource:
          product: macos
          category: process_creation
        detection:
          selection:
            ProcessName: osascript
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == {"process.name": "osascript"}


def test_product_match_is_case_insensitive():
    from nextron_valhalla_sigma_rules_modules.ecs_field_maps import mapping_for_product

    assert mapping_for_product("Windows") is RAW_TO_ECS_BY_PRODUCT["windows"]
    assert mapping_for_product("okta") is RAW_TO_ECS
    assert mapping_for_product(None) is RAW_TO_ECS


WINDOWS_ONLY_FIELDS = [
    ("ObjectClass", "action.properties.ObjectClass"),
    ("Details", "action.properties.Details"),
    ("GrantedAccess", "action.properties.GrantedAccess"),
    ("Status", "action.properties.Status"),
    ("Category", "action.properties.Category"),
    ("Level", "action.properties.Level"),
    ("Path", "action.properties.Path"),
    ("SubjectUserName", "user.name"),
    ("TargetUserName", "user.target.name"),
    ("TargetUserSid", "user.target.id"),
    ("Signature", "action.properties.Signature"),
    ("Signed", "action.properties.Signed"),
]


@pytest.mark.parametrize("raw,ecs", WINDOWS_ONLY_FIELDS)
def test_windows_only_fields_map_for_windows_rules(raw, ecs):
    payload = _single_field_rule(raw, product="windows")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert ecs in converted["detection"]["selection"]


@pytest.mark.parametrize("raw", ["Status", "Category", "Level", "Path", "Details"])
@pytest.mark.parametrize("product", ["okta", None])
def test_windows_event_data_catch_alls_are_unmapped_elsewhere(raw, product):
    """S10: an Okta rule using ``Status`` must not be accepted with a
    Windows ``action.properties.Status`` target that never matches."""
    payload = _single_field_rule(raw, product=product)
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == [raw]


# ---------------------------------------------------------------------------
# Context-aware PE metadata (SigmaHQ ecs_windows_variable_mappings)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,category,expected",
    [
        # Verified against the Sekoia Windows parser fixtures: PE metadata
        # stays in action.properties.* for both process_creation and
        # image_load.
        ("Description", "process_creation", "action.properties.Description"),
        ("Description", "image_load", "action.properties.Description"),
        ("Product", "process_creation", "action.properties.Product"),
        ("Product", "image_load", "action.properties.Product"),
        ("Company", "process_creation", "action.properties.Company"),
        ("Company", "image_load", "action.properties.Company"),
        ("OriginalFileName", "process_creation", "action.properties.OriginalFileName"),
        ("OriginalFileName", "image_load", "action.properties.OriginalFileName"),
        ("FileVersion", "process_creation", "action.properties.FileVersion"),
        ("FileVersion", "image_load", "action.properties.FileVersion"),
        ("Description", "sysmon_error", "action.properties.Description"),
        ("Protocol", "network_connection", "network.transport"),
        # C3: ImageLoad → dll.*, DriverLoad → process.*
        ("ImageLoaded", "image_load", "dll.path"),
        ("ImageLoaded", "driver_load", "process.executable"),
        ("Imphash", "process_creation", "process.pe.imphash"),
        ("Imphash", "image_load", "dll.pe.imphash"),
    ],
)
def test_context_aware_field_maps_by_category(field, category, expected):
    payload = _rule_with_logsource(category, f"{field}|contains: 'x'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted is not None
    selection = converted["detection"]["selection"]
    assert f"{expected}|contains" in selection


def test_initiated_is_unmapped():
    """S8: the parser has no ``Initiated`` field; ``network.direction`` holds
    ingress/egress, never ``'true'``."""
    payload = _rule_with_logsource("network_connection", "Initiated: 'true'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["Initiated"]


def test_context_aware_field_without_matching_category_is_unmapped():
    """A rule using Description without a matching logsource.category should
    be skipped, mirroring SigmaHQ's conditional-mapping behaviour."""
    payload = _rule_with_logsource("some_other_category", "Description|contains: 'x'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["Description"]


@pytest.mark.parametrize("category", ["driver_load", "image_load", "process_creation"])
def test_signature_maps_to_action_properties(category):
    payload = _rule_with_logsource(category, "Signature|contains: 'Microsoft'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert "action.properties.Signature|contains" in converted["detection"]["selection"]


@pytest.mark.parametrize(
    "raw,ecs,product",
    [
        ("eventType", "event.action", None),
        ("EventType", "event.action", None),
        ("OperationName", "event.action", None),
        ("a2", "auditd.data.a2", None),
        ("a3", "auditd.data.a3", None),
        ("a4", "auditd.data.a4", None),
        ("Data", "action.properties.Data", "windows"),
        ("ObjectName", "action.properties.ObjectName", "windows"),
        ("ObjectType", "action.properties.ObjectType", "windows"),
        ("ShareName", "action.properties.ShareName", "windows"),
        ("AccessMask", "action.properties.AccessMask", "windows"),
        ("TaskName", "action.properties.TaskName", "windows"),
        ("Contents", "action.properties.Contents", "windows"),
        ("ContextInfo", "action.properties.ContextInfo", "windows"),
    ],
)
def test_custom_map_additions_are_reachable(raw, ecs, product):
    payload = _single_field_rule(raw, product=product)
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted is not None
    assert ecs in converted["detection"]["selection"]


def test_gcp_audit_fields_pass_through_as_ecs():
    """Some Sigma rules already use ECS-shaped GCP audit field names.
    They should be recognised without modification."""
    payload = _single_field_rule("gcp.audit.method_name")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert "gcp.audit.method_name" in converted["detection"]["selection"]


# ---------------------------------------------------------------------------
# Stage 2 — TargetObject context-dependent + Hashes value split
# ---------------------------------------------------------------------------


def _rule_with_logsource(category: str, selection_body: str) -> str:
    return textwrap.dedent(
        f"""\
        title: T
        logsource:
          product: windows
          category: {category}
        detection:
          selection:
            {selection_body}
          condition: selection
        """
    )


@pytest.mark.parametrize(
    "category,expected_ecs",
    [
        ("registry_set", "registry.path"),
        ("registry_add", "registry.path"),
        ("registry_delete", "registry.path"),
        ("registry_rename", "registry.path"),
        ("registry_event", "registry.path"),
        ("file_event", "file.path"),
    ],
)
def test_target_object_maps_by_logsource_category(category, expected_ecs):
    payload = _rule_with_logsource(category, "TargetObject|contains: 'foo'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    assert f"{expected_ecs}|contains" in parsed["detection"]["selection"]


def test_target_object_unknown_logsource_is_unmapped():
    payload = _rule_with_logsource("weird_category", "TargetObject|contains: 'foo'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["TargetObject"]


def test_target_object_without_logsource_category_is_unmapped():
    """Sanity: a rule with no logsource.category can't resolve TargetObject."""
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            TargetObject|contains: 'foo'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["TargetObject"]


def test_hashes_single_value_splits_to_ecs():
    payload = _hashes_rule("'IMPHASH=abc123'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    sel = converted["detection"]["selection"]
    assert sel == {"process.pe.imphash|contains": "abc123"}


def test_hashes_list_of_same_algo_preserves_list():
    payload = _hashes_rule("\n      - 'IMPHASH=abc'\n      - 'IMPHASH=def'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == {"process.pe.imphash|contains": ["abc", "def"]}


def test_hashes_mixed_algos_become_or_list_of_maps():
    """C2: ``Hashes|contains: [MD5=a, SHA1=b, SHA256=c]`` is an OR. It becomes a
    list of maps (Sigma OR), each carrying the selection's other keys."""
    payload = _hashes_rule(
        "\n      - 'MD5=aaaa'\n      - 'SHA1=bbbb'\n      - 'SHA256=cccc'", extra="Image|endswith: '.exe'"
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == [
        {"process.executable|endswith": ".exe", "process.hash.md5|contains": "aaaa"},
        {"process.executable|endswith": ".exe", "process.hash.sha1|contains": "bbbb"},
        {"process.executable|endswith": ".exe", "process.hash.sha256|contains": "cccc"},
    ]


def _matches(selection, event: dict) -> bool:
    """Tiny evaluator for the shapes the converter emits (|contains only)."""
    if isinstance(selection, list):
        return any(_matches(s, event) for s in selection)
    for key, value in selection.items():
        field = key.split("|")[0]
        values = value if isinstance(value, list) else [value]
        if not any(str(v).lower() in str(event.get(field, "")).lower() for v in values):
            return False
    return True


def test_hashes_or_matches_event_without_sha1():
    """C2: Sysmon configs commonly log MD5/SHA256/IMPHASH but not SHA1. A
    rule listing a SHA1 must still match on the MD5."""
    payload = _hashes_rule("\n      - 'MD5=aaaa'\n      - 'SHA1=bbbb'")
    converted, _ = convert_payload_to_ecs(payload)
    event = {"process.hash.md5": "aaaa", "process.hash.sha256": "ffff"}
    assert _matches(converted["detection"]["selection"], event)


def test_hashes_all_modifier_keeps_and():
    payload = _hashes_rule("\n      - 'MD5=aaaa'\n      - 'SHA256=bbbb'", mods="|contains|all")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == {
        "process.hash.md5|contains|all": "aaaa",
        "process.hash.sha256|contains|all": "bbbb",
    }


def test_hashes_inside_list_of_maps_is_spliced():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            - Hashes|contains: ['MD5=a', 'SHA256=b']
            - Image|endswith: x.exe
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == [
        {"process.hash.md5|contains": "a"},
        {"process.hash.sha256|contains": "b"},
        {"process.executable|endswith": "x.exe"},
    ]


@pytest.mark.parametrize(
    "category,expected",
    [
        ("image_load", {"dll.hash.md5|contains": "a", "dll.pe.imphash|contains": "c"}),
        ("file_delete", {"file.hash.md5|contains": "a", "file.pe.imphash|contains": "c"}),
    ],
)
def test_hash_targets_depend_on_category(category, expected):
    """C3: ImageLoad hashes are ``dll.*``, file-hash events ``file.*``; SHA1
    doesn't exist there and is dropped from the OR."""
    payload = _rule_with_logsource(category, "Hashes|contains: ['MD5=a', 'SHA1=b', 'IMPHASH=c']")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    sel = converted["detection"]["selection"]
    assert {k: v for branch in sel for k, v in branch.items()} == expected


def test_hashes_with_only_unavailable_algos_is_unmapped():
    payload = _rule_with_logsource("image_load", "Hashes|contains: 'SHA1=b'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["Hashes"]


def test_hashes_comma_separated_single_string():
    payload = _hashes_rule("'MD5=aaaa,SHA1=bbbb'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == [
        {"process.hash.md5|contains": "aaaa"},
        {"process.hash.sha1|contains": "bbbb"},
    ]


def _hashes_rule(value: str, extra: str = "", mods: str = "|contains") -> str:
    extra_line = f"    {extra}\n" if extra else ""
    return f"title: T\ndetection:\n  selection:\n{extra_line}    Hashes{mods}: {value}\n  condition: selection\n"


def test_fieldref_value_is_resolved():
    """S7: the ``|fieldref`` value names a field and is rewritten too."""
    payload = _single_field_rule("ParentImage|fieldref", "Image", product="windows")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == {"process.parent.executable|fieldref": "process.executable"}


def test_fieldref_to_unknown_field_is_unmapped():
    payload = _single_field_rule("ParentImage|fieldref", "NoSuchField", product="windows")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["NoSuchField"]


def test_hashes_alongside_other_fields_still_splits():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Image|endswith: '\\evil.exe'
            Hashes|contains: 'MD5=aaaa'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    sel = parsed["detection"]["selection"]
    assert "process.executable|endswith" in sel
    assert sel["process.hash.md5|contains"] == "aaaa"


def test_hashes_unknown_algo_is_unmapped():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Hashes|contains: 'CUSTOM_HASH=abc'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["Hashes"]


def test_hashes_malformed_value_is_unmapped():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Hashes|contains: 'no-equals-sign'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert "Hashes" in unmapped


def test_bare_all_modifier_in_keywords_block_is_preserved():
    """Sigma keyword-modifier construct: ``keywords: {'|all': [...]}``
    means AND-match all listed substrings against the raw event. The
    ``|all`` key has no field name and must pass through unchanged, not
    be flagged as an unmapped field."""
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          condition: keywords
          keywords:
            '|all':
              - foo
              - bar
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["keywords"] == {"|all": ["foo", "bar"]}


def test_hashes_bare_field_no_modifier_still_splits():
    """`Hashes` without a modifier (equality match) still splits."""
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Hashes: 'MD5=aaaa'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    sel = parsed["detection"]["selection"]
    assert sel["process.hash.md5"] == "aaaa"


# ---------------------------------------------------------------------------
# Second review round: tags, references
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tag,expected_label",
    [("attack.command_and_control", "attack.command-and-control"), ("attack.initial_access", "attack.initial-access")],
)
def test_underscore_tactic_tags_are_recognised(tag, expected_label):
    """S12: ``attack.command_and_control`` is the same tactic as the
    hyphenated spelling."""
    from nextron_valhalla_sigma_rules_modules.sigma_mapper import TAG_ALERT_UUID_MAP, derive_alert_type_uuid

    expected = dict(TAG_ALERT_UUID_MAP)[expected_label]
    assert derive_alert_type_uuid([tag]) == expected


def test_references_are_appended_to_description():
    rule, parsed = _rule_and_parsed(
        "title: t\ndescription: Detects X.\nreferences:\n  - https://a.example\n  - https://b.example\ndetection: {}\n"
    )
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["description"] == "Detects X.\n\nReferences:\n- https://a.example\n- https://b.example"


def test_references_respect_description_limit():
    refs = "".join(f"  - https://example.com/{'x' * 80}/{i}\n" for i in range(30))
    rule, parsed = _rule_and_parsed(f"title: t\ndescription: d\nreferences:\n{refs}detection: {{}}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert len(body["description"]) == MAX_DESCRIPTION_LENGTH


def test_rpc_firewall_rules_use_the_windows_map():
    """RPC Firewall logs arrive through the Windows event-log parser, so its
    ``event_data`` catch-alls apply."""
    payload = _single_field_rule("InterfaceUuid", "'abc'", product="rpc_firewall")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted["detection"]["selection"] == {"action.properties.InterfaceUuid": "abc"}


def test_windows_map_still_resolves_commandline():
    """SigmaHQ's Windows map has no ``CommandLine``; the other SigmaHQ maps
    fill that gap for every product."""
    for product in ("windows", "macos", "linux", None):
        payload = _single_field_rule("CommandLine|contains", "'x'", product=product)
        converted, unmapped = convert_payload_to_ecs(payload)
        assert unmapped == [], product
        assert "process.command_line|contains" in converted["detection"]["selection"]
