import textwrap

import pytest
import yaml

from nextron_valhalla_sigma_rules_modules.sigma_mapper import (
    DEFAULT_EFFORT,
    DEFAULT_SEVERITY,
    MARKER_TAG,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    RAW_TO_ECS,
    SEVERITY_MAP,
    STATUS_EFFORT_MAP,
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
    assert body["effort"] == DEFAULT_EFFORT  # no status field → default
    # No tactic tag → default alert type (application-compromise).
    assert body["alert_type_uuid"] == "599f4b1a-dd60-43fe-8ee9-07d3c5d00ded"
    assert body["enabled"] is False


def test_payload_is_detection_only():
    """The `payload` string must contain the ECS-converted detection block
    (with the `detection:` keyword) and NOT any of the surrounding metadata."""
    rule, parsed = _rule_and_parsed(HIGH_RULE_YAML)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)

    assert body["payload"].lstrip().startswith("detection:")
    assert "title:" not in body["payload"]
    assert "description:" not in body["payload"]
    assert "references:" not in body["payload"]
    assert "level:" not in body["payload"]


def test_payload_roundtrips_back_to_a_detection_block():
    rule, parsed = _rule_and_parsed(HIGH_RULE_YAML)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)

    reparsed = yaml.safe_load(body["payload"])
    assert set(reparsed.keys()) == {"detection"}
    assert "condition" in reparsed["detection"]
    assert "selection" in reparsed["detection"]


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
    rule, parsed = _rule_and_parsed(f"title: t\nlevel: {level}\ndetection: {{selection: {{a: 1}}, condition: selection}}\n")
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


@pytest.mark.parametrize(
    "status,expected",
    [
        ("stable", 1),
        ("test", 2),
        ("experimental", 3),
        ("unsupported", 4),
        ("deprecated", 4),
        ("STABLE", 1),  # case-insensitive
    ],
)
def test_effort_from_status(status, expected):
    rule, parsed = _rule_and_parsed(f"title: t\nstatus: {status}\ndetection: {{}}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["effort"] == expected


def test_effort_defaults_when_status_missing():
    rule, parsed = _rule_and_parsed("title: t\ndetection: {}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["effort"] == DEFAULT_EFFORT == 3


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
        "CVE-2023-1389 Potential Exploitation Attempt - Unauthenticated "
        "Command Injection In TP-Link Archer AX21"
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
    rule, parsed = _rule_and_parsed(
        f"title: t\ndescription: {long_desc}\ndetection: {{}}\n"
    )
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert len(body["description"]) <= MAX_DESCRIPTION_LENGTH
    assert body["description"].endswith("…")


def test_description_at_exact_limit_is_untouched():
    desc = "y" * MAX_DESCRIPTION_LENGTH
    rule, parsed = _rule_and_parsed(
        f"title: t\ndescription: {desc}\ndetection: {{}}\n"
    )
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
    yaml_body = (
        "title: t\n"
        "tags:\n  - attack.credential-access\n  - cve.2023-1389\n"
        "detection: {}\n"
    )
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["tags"] == [
        "attack.credential-access",
        "cve.2023-1389",
        MARKER_TAG,
    ]


def test_marker_tag_is_added_when_source_has_no_tags():
    rule, parsed = _rule_and_parsed("title: t\ndetection: {}\n")
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["tags"] == [MARKER_TAG]


def test_marker_tag_is_not_duplicated():
    yaml_body = (
        "title: t\n"
        f"tags:\n  - {MARKER_TAG}\n  - attack.t1059\n"
        "detection: {}\n"
    )
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["tags"].count(MARKER_TAG) == 1


def test_datasources_not_shipped_even_when_logsource_present():
    # Sekoia's `datasources` is a list of tenant-registered data-source UUIDs,
    # not the Sigma logsource dict. We can't derive UUIDs from `{product,
    # category}`, so the field is intentionally omitted.
    yaml_body = (
        "title: t\n"
        "logsource:\n  product: windows\n  category: process_creation\n"
        "detection: {}\n"
    )
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert "datasources" not in body


def test_related_object_refs_is_never_shipped():
    """Sigma's `related` list carries Sigma-world UUIDs that don't map to
    anything in Sekoia's tenant catalog — shipping them as
    `related_object_refs` would just add dangling references. Field is
    intentionally omitted."""
    yaml_body = (
        "title: t\n"
        "related:\n"
        "  - id: 8cf4da11-0d3b-4a4f-9f5f-abcdef012345\n"
        "    type: obsoletes\n"
        "detection: {}\n"
    )
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert "related_object_refs" not in body


def test_false_positives_list_is_joined_with_newlines():
    yaml_body = (
        "title: t\n"
        "falsepositives:\n"
        "  - Legit scanners\n"
        "  - IT admin scripts\n"
        "  - Backup jobs\n"
        "detection: {}\n"
    )
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
    assert body["effort"] == 1
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
    assert derive_alert_type_uuid(
        ["attack.persistence", "attack.exfiltration"]
    ) == exfiltration_uuid
    # Order in the tag list must not matter — priority list is authoritative.
    assert derive_alert_type_uuid(
        ["attack.exfiltration", "attack.persistence"]
    ) == exfiltration_uuid
    # Sanity: backdoor is what persistence alone yields.
    assert derive_alert_type_uuid(["attack.persistence"]) == backdoor_uuid


def test_case_insensitive_tag_matching():
    exfiltration_uuid = "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"
    assert derive_alert_type_uuid(["ATTACK.EXFILTRATION"]) == exfiltration_uuid


def test_non_string_tag_entries_are_ignored():
    # Defensive: tags list occasionally contains non-strings from odd YAML.
    exfiltration_uuid = "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"
    assert derive_alert_type_uuid(
        [None, 123, "attack.exfiltration"]
    ) == exfiltration_uuid


def test_marker_tag_alone_does_not_override_default():
    # The marker tag must not accidentally match any priority-list entry.
    from nextron_valhalla_sigma_rules_modules.sigma_mapper import MARKER_TAG
    assert derive_alert_type_uuid([MARKER_TAG]) == DEFAULT_ALERT_UUID


def test_body_alert_type_uuid_derived_from_tags():
    """End-to-end: a rule tagged attack.exfiltration ends up with the
    exfiltration alert_type_uuid in the POSTed body."""
    yaml_body = (
        "title: t\n"
        "tags: [attack.exfiltration, attack.t1041]\n"
        "detection: {}\n"
    )
    rule, parsed = _rule_and_parsed(yaml_body)
    body = sigma_rule_to_catalog_payload(rule, parsed, enabled=False)
    assert body["alert_type_uuid"] == "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"


# ---------------------------------------------------------------------------
# convert_payload_to_ecs — Stage 1 conversion
# ---------------------------------------------------------------------------


def _single_field_rule(field: str, value: str = "'foo'") -> str:
    return textwrap.dedent(
        f"""\
        title: T
        detection:
          selection:
            {field}: {value}
          condition: selection
        """
    )


@pytest.mark.parametrize(
    "raw,ecs",
    [
        # SigmaHQ Windows pipeline (source of truth)
        ("Image", "process.executable"),               # .caseless stripped
        ("CommandLine", "process.command_line"),
        ("ParentImage", "process.parent.executable"),  # .caseless stripped
        ("ParentCommandLine", "process.parent.command_line"),
        ("EventID", "event.code"),
        ("TargetFilename", "file.path"),
        ("ImageLoaded", "file.path"),                  # SigmaHQ target (was dll.path)
        ("ScriptBlockText", "powershell.file.script_block_text"),
        ("DestinationIp", "destination.ip"),
        ("QueryName", "dns.question.name"),
        ("User", "user.name"),
        ("Signed", "file.code_signature.signed"),      # SigmaHQ prefixes with `file.`
        ("SignatureStatus", "file.code_signature.status"),
        ("TargetUserName", "user.target.name"),
        ("TargetDomainName", "user.target.domain"),
        ("TargetUserSid", "user.target.id"),
        ("Imphash", "file.pe.imphash"),
        # Web / proxy W3C ELF fields (Zeek pipeline)
        ("cs-method", "http.request.method"),
        ("cs-referer", "http.request.referrer"),
        ("cs-uri-query", "url.query"),
        ("cs-uri-stem", "url.original"),               # Zeek target (was url.path)
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
        # Windows security event_data (custom)
        ("ObjectClass", "action.properties.ObjectClass"),
        ("ObjectDN", "action.properties.ObjectDN"),
        ("Details", "action.properties.Details"),
        ("SubjectUserName", "user.name"),
        ("LogonType", "action.properties.LogonType"),
        ("GrantedAccess", "action.properties.GrantedAccess"),
        ("CallTrace", "action.properties.CallTrace"),
        ("InterfaceUuid", "action.properties.InterfaceUuid"),
        ("IsatapRouter", "action.properties.IsatapRouter"),
        ("FilterName", "action.properties.FilterName"),
        ("LogonId", "action.properties.LogonId"),
        ("LogonProcessName", "action.properties.LogonProcessName"),
        ("ObjectServer", "action.properties.ObjectServer"),
        ("ObjectValueName", "action.properties.ObjectValueName"),
        ("PrivilegeList", "action.properties.PrivilegeList"),
        ("SamAccountName", "action.properties.SamAccountName"),
        ("SourceName", "action.properties.SourceName"),
        ("SubjectUserSid", "action.properties.SubjectUserSid"),
        ("TargetName", "action.properties.TargetName"),
        ("TaskContent", "action.properties.TaskContent"),
        ("TicketEncryptionType", "action.properties.TicketEncryptionType"),
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
    assert (
        "process.command_line|contains|base64offset"
        in parsed["detection"]["selection"]
    )


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
    assert all(
        "process.executable|endswith" in item
        for item in parsed["detection"]["selection"]
    )


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
    converted, unmapped = convert_payload_to_ecs(
        payload, mapping={"Foo": "custom.ecs.field"}
    )
    assert unmapped == []
    parsed = converted
    assert "custom.ecs.field|contains" in parsed["detection"]["selection"]


def test_raw_to_ecs_map_has_no_duplicate_targets_for_process_executable():
    """Sanity check: multiple raw names map to the same ECS target intentionally."""
    process_exec = [
        k for k, v in RAW_TO_ECS.items() if v == "process.executable"
    ]
    # Image, SourceImage, TargetImage, ImagePath all map here
    assert set(process_exec) >= {"Image", "SourceImage", "TargetImage", "ImagePath"}


# ---------------------------------------------------------------------------
# Provenance — SigmaHQ pipelines vs. Custom
# ---------------------------------------------------------------------------


def test_sigmahq_pipelines_load_without_caseless_suffix():
    """Sekoia's ECS schema doesn't expose `.caseless` sub-fields; the merge
    strips the suffix. Confirm no runtime target still carries it."""
    for target in RAW_TO_ECS.values():
        assert not target.endswith(".caseless"), target


def test_windows_wins_shared_field_names_over_macos():
    """User, ProcessName, ParentImage etc. exist in both SigmaHQ Windows
    and macOS pipelines with different targets. The merge order puts
    Windows first so Windows-appropriate ECS targets win — Valhalla's
    feed is majority Windows."""
    from nextron_valhalla_sigma_rules_modules.ecs_field_maps import (
        RAW_TO_ECS_SIGMAHQ_MACOS,
        RAW_TO_ECS_SIGMAHQ_WINDOWS,
    )
    shared = set(RAW_TO_ECS_SIGMAHQ_WINDOWS) & set(RAW_TO_ECS_SIGMAHQ_MACOS)
    assert shared, "Expected shared field names between Windows and macOS"
    for k in shared:
        # After merge, the target should match Windows (stripped of .caseless).
        expected = RAW_TO_ECS_SIGMAHQ_WINDOWS[k].removesuffix(".caseless")
        assert RAW_TO_ECS[k] == expected, k


def test_custom_map_fills_gaps_windows_pipeline_doesnt_cover():
    from nextron_valhalla_sigma_rules_modules.ecs_field_maps import (
        RAW_TO_ECS_CUSTOM,
        RAW_TO_ECS_SIGMAHQ_WINDOWS,
    )
    # CUSTOM's TargetImage should surface in the runtime map (Windows
    # doesn't have TargetImage in its static dict).
    assert "TargetImage" not in RAW_TO_ECS_SIGMAHQ_WINDOWS
    assert "TargetImage" in RAW_TO_ECS_CUSTOM
    assert RAW_TO_ECS["TargetImage"] == RAW_TO_ECS_CUSTOM["TargetImage"]


# ---------------------------------------------------------------------------
# Context-aware PE metadata (SigmaHQ ecs_windows_variable_mappings)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,category,expected",
    [
        # PE fields differ between process_creation and image_load contexts.
        ("Description", "process_creation", "process.pe.description"),
        ("Description", "image_load", "file.pe.description"),
        ("Product", "process_creation", "process.pe.product"),
        ("Product", "image_load", "file.pe.product"),
        ("Company", "process_creation", "process.pe.company"),
        ("Company", "image_load", "file.pe.company"),
        ("OriginalFileName", "process_creation", "process.pe.original_file_name"),
        ("OriginalFileName", "image_load", "file.pe.original_file_name"),
        ("FileVersion", "process_creation", "process.pe.file_version"),
        ("FileVersion", "image_load", "file.pe.file_version"),
        # Description has a third category (sysmon_error) per SigmaHQ.
        ("Description", "sysmon_error", "action.properties.Description"),
        # Initiated / Protocol are network_connection-only.
        ("Initiated", "network_connection", "network.direction"),
        ("Protocol", "network_connection", "network.transport"),
    ],
)
def test_context_aware_field_maps_by_category(field, category, expected):
    payload = _rule_with_logsource(
        category, f"{field}|contains: 'x'"
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted is not None
    selection = converted["detection"]["selection"]
    assert f"{expected}|contains" in selection


def test_context_aware_field_without_matching_category_is_unmapped():
    """A rule using Description without a matching logsource.category should
    be skipped, mirroring SigmaHQ's conditional-mapping behaviour."""
    payload = _rule_with_logsource("some_other_category", "Description|contains: 'x'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert converted is None
    assert unmapped == ["Description"]


@pytest.mark.parametrize(
    "category",
    ["driver_loaded", "image_loaded", "process_creation", "some_random_category"],
)
def test_signature_maps_statically_regardless_of_category(category):
    """SigmaHQ makes ``Signature`` context-aware, but both variants map to
    the same target. We collapse it to a static CUSTOM entry so rules
    outside driver_loaded/image_loaded still convert."""
    payload = _rule_with_logsource(category, "Signature|contains: 'Microsoft'")
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    assert converted is not None
    assert (
        "file.code_signature.subject_name|contains"
        in converted["detection"]["selection"]
    )


@pytest.mark.parametrize(
    "raw,ecs",
    [
        # AWS variants added to CUSTOM
        ("eventType", "event.action"),
        ("EventType", "event.action"),
        ("OperationName", "event.action"),
        # Auditd extras
        ("a2", "auditd.data.a2"),
        ("a3", "auditd.data.a3"),
        ("a4", "auditd.data.a4"),
        # Windows Security event_data
        ("Data", "action.properties.Data"),
        ("ObjectName", "action.properties.ObjectName"),
        ("ObjectType", "action.properties.ObjectType"),
        ("ShareName", "action.properties.ShareName"),
        ("AccessMask", "action.properties.AccessMask"),
        ("Status", "action.properties.Status"),
        ("TaskName", "action.properties.TaskName"),
        ("Category", "action.properties.Category"),
        ("Level", "action.properties.Level"),
        ("Path", "action.properties.Path"),
        ("Contents", "action.properties.Contents"),
        ("ContextInfo", "action.properties.ContextInfo"),
    ],
)
def test_custom_map_additions_are_reachable(raw, ecs):
    payload = _single_field_rule(raw)
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
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Hashes|contains: 'IMPHASH=abc123'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    sel = parsed["detection"]["selection"]
    assert "process.hash.imphash|contains" in sel
    assert sel["process.hash.imphash|contains"] == "abc123"
    assert "Hashes" not in sel and "Hashes|contains" not in sel


def test_hashes_list_of_same_algo_preserves_list():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Hashes|contains:
              - 'IMPHASH=abc'
              - 'IMPHASH=def'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    sel = parsed["detection"]["selection"]
    assert sel["process.hash.imphash|contains"] == ["abc", "def"]


def test_hashes_mixed_algos_split_to_multiple_ecs_keys():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Hashes|contains:
              - 'MD5=aaaa'
              - 'SHA256=bbbb'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    sel = parsed["detection"]["selection"]
    assert sel["process.hash.md5|contains"] == "aaaa"
    assert sel["process.hash.sha256|contains"] == "bbbb"


def test_hashes_comma_separated_single_string():
    payload = textwrap.dedent(
        """\
        title: T
        detection:
          selection:
            Hashes|contains: 'MD5=aaaa,SHA1=bbbb'
          condition: selection
        """
    )
    converted, unmapped = convert_payload_to_ecs(payload)
    assert unmapped == []
    parsed = converted
    sel = parsed["detection"]["selection"]
    assert sel["process.hash.md5|contains"] == "aaaa"
    assert sel["process.hash.sha1|contains"] == "bbbb"


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
