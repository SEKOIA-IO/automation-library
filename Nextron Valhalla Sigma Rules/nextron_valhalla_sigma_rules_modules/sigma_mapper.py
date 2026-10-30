import re

import yaml

from nextron_valhalla_sigma_rules_modules.ecs_field_maps import (
    _ECS_PASSTHROUGH_FIELDS,
    CONTEXT_AWARE_FIELDS,
    HASH_TARGETS_BY_CATEGORY,
    HASH_TARGETS_DEFAULT,
    mapping_for_product,
)

SEVERITY_MAP = {
    "informational": 10,
    "low": 30,
    "medium": 50,
    "high": 70,
    "critical": 90,
}
# Returned when the Sigma rule has no ``level`` field at all.
DEFAULT_SEVERITY = 0

# Sigma maturity order used by the sync trigger's ``min_sigma_status``
# filter: a rule passes when its rank is ``>=`` the configured one.
# ``deprecated`` / ``unsupported`` are absent on purpose — never imported.
STATUS_RANK = {
    "experimental": 1,
    "test": 2,
    "stable": 3,
}

# Sekoia's ``effort`` (1-4) is the expected analysis effort of an alert —
# Sigma has no equivalent, so every rule gets the same value. The field is
# required on create and update. The Sigma maturity is carried as a tag
# instead (``status-<status>``).
RULE_EFFORT = 2
STATUS_TAG_PREFIX = "status-"

# Sekoia Rules Catalog API rejects (HTTP 400 VA301) rule names longer than
# 100 characters. Truncate defensively and mark truncation with a single-char
# Unicode ellipsis so operators can still recognise the rule.
MAX_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 1000
_TRUNCATION_MARKER = "…"

# Marker tag appended to every rule the sync trigger POSTs so operators can
# identify rules created by this integration independently of the Sekoia
# API key that created them (``created_by`` changes on key rotation; a tag
# does not).
MARKER_TAG = "nextron-valhalla"

# Per-rule tag prefix carrying the Valhalla rule UUID. Lets the sync trigger
# recover the valhalla_id → sekoia_uuid mapping from the catalog itself when
# the local id-map is empty (fresh playbook, recreated trigger instance,
# wiped data volume). Prefix uses ``-`` instead of ``:`` to stay inside the
# character set Sekoia accepts on tag names.
UUID_TAG_PREFIX = "uuid-"

# Sekoia alert-type UUIDs are stable across tenants (Ecsirt-standard
# taxonomy). We derive an ``alert_type_uuid`` per rule from its Sigma
# MITRE tactic tags rather than requiring a user-supplied config value.
DEFAULT_ALERT_UUID = "599f4b1a-dd60-43fe-8ee9-07d3c5d00ded"  # application-compromise

# Priority-ordered list: first matching tag wins. Later kill-chain
# stages beat earlier ones; specific detections (c&c, exfiltration)
# beat generic categories.
TAG_ALERT_UUID_MAP: tuple[tuple[str, str], ...] = (
    ("attack.exfiltration", "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"),  # exfiltration
    ("attack.command-and-control", "47e51ab7-4caa-4c4b-8442-a1caf868806d"),  # c&c
    ("attack.persistence", "5928d144-2038-4a87-b996-b3585a9a1a41"),  # backdoor
    ("attack.initial-access", "4321cd89-89d6-4674-9e99-690ce0e61621"),  # exploit
    ("attack.discovery", "38305ebd-cec9-47ff-b38b-d20bd22eb79d"),  # appscan
    ("attack.reconnaissance", "38305ebd-cec9-47ff-b38b-d20bd22eb79d"),  # appscan
)


def derive_alert_type_uuid(tags: list) -> str:
    """Return the highest-priority alert_type_uuid the Sigma tags map
    to, or ``DEFAULT_ALERT_UUID`` if no tactic tag matches.

    Tactic tags are matched case-insensitively and with ``_`` treated as
    ``-`` (``attack.command_and_control`` == ``attack.command-and-control``).
    """
    tag_set = {t.lower().replace("_", "-") for t in tags if isinstance(t, str)}
    for tag, uuid in TAG_ALERT_UUID_MAP:
        if tag in tag_set:
            return uuid
    return DEFAULT_ALERT_UUID


# Sigma Hashes values look like ``ALGO=DIGEST``. The ECS target per algo
# depends on the rule's category (see ``HASH_TARGETS_BY_CATEGORY``).
_HASH_ALGOS: frozenset[str] = frozenset({"md5", "sha1", "sha256", "sha512", "imphash"})

# Field key like "CommandLine" or "cs-uri-query|contains|base64offset".
# Field names allow letters, digits, underscore, dot, and hyphen (for W3C ELF
# style names such as `cs-method`).
_FIELD_KEY_RE = re.compile(r"^([A-Za-z0-9_.\-]+)((?:\|[a-z0-9_]+)*)$")

# Sigma also allows bare-modifier keys inside a selection dict — used in
# implicit-keyword blocks like ``keywords: {'|all': [foo, bar]}`` where the
# ``|all`` modifier applies to the enclosing block's values, not to a named
# field. We preserve these keys as-is.
_BARE_MODIFIER_RE = re.compile(r"^((?:\|[a-z0-9_]+)+)$")

# Keys under `detection:` that are not selection blocks and must not be walked.
_NON_SELECTION_KEYS = frozenset({"condition", "timeframe"})


def _split_field_key(key: str) -> tuple[str, str]:
    """Split ``"Field|mod1|mod2"`` into ``("Field", "|mod1|mod2")``.

    Bare-modifier keys like ``"|all"`` (Sigma keyword-modifier construct
    with no field name) return ``("", "|all")`` so the caller can preserve
    the key unchanged.

    Returns the whole key as the field name and empty modifiers if the input
    doesn't match either expected shape (defensive — unusual keys pass through
    unchanged so the caller can decide what to do).
    """
    m = _FIELD_KEY_RE.match(key)
    if m:
        return m.group(1), m.group(2) or ""
    if _BARE_MODIFIER_RE.match(key):
        return "", key
    return key, ""


def _resolve_field(
    bare: str,
    mapping: dict[str, str],
    logsource_category: str | None,
) -> str | None:
    """Return the ECS field name for ``bare``, or ``None`` if unmapped.

    Consults ``CONTEXT_AWARE_FIELDS`` first (Sigma fields whose ECS
    target depends on ``logsource.category`` — TargetObject and the
    Windows PE-metadata + Signature/Initiated/Protocol variants).
    Falls back to ``_ECS_PASSTHROUGH_FIELDS`` for values that Stage 2
    already produced in ECS shape, then to the flat ``mapping`` (the
    merged SigmaHQ + custom map).
    """
    if bare in CONTEXT_AWARE_FIELDS:
        return CONTEXT_AWARE_FIELDS[bare].get(logsource_category or "")
    if bare in _ECS_PASSTHROUGH_FIELDS:
        return bare
    return mapping.get(bare)


def _parse_hash_values(value) -> list[tuple[str, str]] | None:
    """Parse a Sigma ``Hashes`` value into ``[(algo_lower, digest), ...]``.

    Accepts either a single string like ``"MD5=abc,SHA256=def"`` or a list of
    such strings. Returns ``None`` if any value doesn't match ``ALGO=DIGEST``
    or the algo is unknown — signals the caller to skip the rule.
    """
    candidates: list[str] = []
    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                return None
            candidates.extend(item.split(","))
    else:
        return None

    result: list[tuple[str, str]] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if "=" not in candidate:
            return None
        algo, digest = candidate.split("=", 1)
        algo = algo.strip().lower()
        digest = digest.strip()
        if algo not in _HASH_ALGOS or not digest:
            return None
        result.append((algo, digest))
    return result or None


def _apply_hashes_transform(
    selection_dict: dict,
    logsource_category: str | None,
    unmapped: list[str],
) -> dict | list[dict]:
    """Rewrite a selection's ``Hashes|<mods>`` key into ECS hash keys.

    Sigma's ``Hashes`` field is a single string (``MD5=…,SHA256=…,IMPHASH=…``)
    and a list value is OR-matched. Sekoia's parser splits it into one field
    per algorithm, so a list mixing algorithms becomes a **list of maps**,
    one per algorithm, each carrying the selection's other keys — Sigma
    reads a list of maps as OR, which keeps the original semantics. A
    single algorithm stays one map (its digests stay an OR-list).

    With the ``|all`` modifier every listed value must match, so the keys
    stay in one map (AND).

    Targets depend on ``logsource.category`` (``process.hash.*``,
    ``dll.hash.*``, ``file.hash.*``). Algorithms the parser never emits for
    that category (e.g. SHA1 on ImageLoad, SHA512 anywhere) are dropped from
    the OR; if none is left — or the value is malformed, or several
    ``Hashes*`` keys share the selection — the rule is marked unmapped.

    Returns the input dict unchanged when it has no ``Hashes*`` key.
    """
    hashes_keys = [k for k in selection_dict if isinstance(k, str) and (k == "Hashes" or k.startswith("Hashes|"))]
    if not hashes_keys:
        return selection_dict
    if len(hashes_keys) > 1:
        unmapped.append("Hashes")
        return selection_dict
    hashes_key = hashes_keys[0]

    _, mods = _split_field_key(hashes_key)
    parsed = _parse_hash_values(selection_dict[hashes_key])
    if parsed is None:
        unmapped.append("Hashes")
        return selection_dict

    targets = HASH_TARGETS_BY_CATEGORY.get(logsource_category or "", HASH_TARGETS_DEFAULT)
    by_target: dict[str, list[str]] = {}
    for algo, digest in parsed:
        target = targets.get(algo)
        if target is not None:
            by_target.setdefault(f"{target}{mods}", []).append(digest)
    if not by_target:
        unmapped.append("Hashes")
        return selection_dict

    rest = {k: v for k, v in selection_dict.items() if k != hashes_key}
    branches: list[dict] = []
    for key, digests in by_target.items():
        if key in rest:
            unmapped.append(f"<collision:{key}>")
            return selection_dict
        branches.append({**rest, key: digests[0] if len(digests) == 1 else digests})
    if len(branches) == 1:
        return branches[0]
    if "|all" in mods:
        merged: dict = dict(rest)
        for branch in branches:
            merged.update({k: v for k, v in branch.items() if k not in rest})
        return merged
    return branches


def _resolve_fieldref_value(value, mapping, unmapped, logsource_category):
    """``Field|fieldref: OtherField`` compares two fields: the value is a
    field name too and must be rewritten like a key."""
    if isinstance(value, list):
        return [_resolve_fieldref_value(v, mapping, unmapped, logsource_category) for v in value]
    if isinstance(value, str):
        mapped = _resolve_field(value, mapping, logsource_category)
        if mapped is None:
            unmapped.append(value)
            return value
        return mapped
    return value


def _convert_selection(
    node,
    mapping: dict[str, str],
    unmapped: list[str],
    logsource_category: str | None = None,
):
    """Recurse into a detection selection block or list of such blocks.

    Applies the Hashes transform, then rewrites field-name keys via
    ``mapping`` while preserving Sigma modifiers. Context-dependent fields
    resolve against ``logsource_category``.

    Anything that would make the converted rule match differently is
    reported in ``unmapped`` (the caller skips the rule):
    - a field with no ECS target;
    - two source keys of one selection resolving to the same ECS key
      (``<collision:…>``) — writing both would silently drop a condition;
    - a ``|fieldref`` value naming an unmappable field.
    """
    if isinstance(node, dict):
        transformed = _apply_hashes_transform(node, logsource_category, unmapped)
        if isinstance(transformed, list):
            return [_convert_selection(item, mapping, unmapped, logsource_category) for item in transformed]

        new_dict: dict = {}
        for k, v in transformed.items():
            if not isinstance(k, str):
                new_dict[k] = _convert_selection(v, mapping, unmapped, logsource_category)
                continue
            bare, mods = _split_field_key(k)
            if not bare:
                # Bare-modifier key like ``|all`` — Sigma keyword-modifier
                # construct with no field name. Preserve.
                new_dict[k] = _convert_selection(v, mapping, unmapped, logsource_category)
                continue
            mapped = _resolve_field(bare, mapping, logsource_category)
            if mapped is None:
                unmapped.append(bare)
                new_key = k
            else:
                new_key = f"{mapped}{mods}"
            if new_key in new_dict:
                unmapped.append(f"<collision:{new_key}>")
                continue
            if "|fieldref" in f"{mods}|":
                new_dict[new_key] = _resolve_fieldref_value(v, mapping, unmapped, logsource_category)
            else:
                new_dict[new_key] = _convert_selection(v, mapping, unmapped, logsource_category)
        return new_dict
    if isinstance(node, list):
        out: list = []
        for item in node:
            converted = _convert_selection(item, mapping, unmapped, logsource_category)
            # A dict item split by the Hashes transform comes back as a list
            # of maps; splice it in so the selection stays one OR-list.
            if isinstance(item, dict) and isinstance(converted, list):
                out.extend(converted)
            else:
                out.append(converted)
        return out
    return node


def convert_parsed_to_ecs(
    parsed: dict,
    mapping: dict[str, str] | None = None,
) -> tuple[dict | None, list[str]]:
    """ECS-convert the ``detection`` block of an already-parsed Sigma rule.

    Only ``parsed["detection"]`` is transformed. Every other field
    (``title``, ``description``, ``level``, ``status``, ``tags``,
    ``logsource``, ``falsepositives``, ``related``, ...) is left unchanged
    so the caller can lift them into structured Sekoia body fields.

    Args:
        parsed: The parsed Sigma rule dict.
        mapping: Field-name mapping to use. Defaults to the map for the
            rule's ``logsource.product`` (see ``mapping_for_product``).

    Returns:
        ``(parsed_rule_dict, [])`` if every field in every selection block
        is resolvable, otherwise ``(None, [unique_unmapped_field_names])``.
        The unmapped list is de-duplicated and sorted for stable output.

        On missing/malformed detection block returns
        ``(None, ["<no-detection>"])``.
    """
    detection = parsed.get("detection")
    if not isinstance(detection, dict):
        return None, ["<no-detection>"]

    logsource = parsed.get("logsource") or {}
    if not isinstance(logsource, dict):
        logsource = {}
    category = logsource.get("category")
    if mapping is None:
        mapping = mapping_for_product(logsource.get("product"))

    unmapped: list[str] = []
    new_detection: dict = {}
    for k, v in detection.items():
        if k in _NON_SELECTION_KEYS:
            new_detection[k] = v
        else:
            new_detection[k] = _convert_selection(v, mapping, unmapped, category)

    if unmapped:
        return None, sorted(set(unmapped))

    result = dict(parsed)
    result["detection"] = new_detection
    return result, []


def convert_payload_to_ecs(
    payload_yaml: str,
    mapping: dict[str, str] | None = None,
) -> tuple[dict | None, list[str]]:
    """YAML-parsing wrapper around :func:`convert_parsed_to_ecs`.

    Only used by the test suite — production code parses YAML once at the
    top of the sync loop and calls :func:`convert_parsed_to_ecs` directly.
    Kept here so tests can exercise the YAML entry-point cases
    (``<yaml-parse-error>``, ``<invalid-root>``) without inlining a parse
    step in every test.

    Returns ``(None, ["<yaml-parse-error>"])`` on YAML parse failure and
    ``(None, ["<invalid-root>"])`` if the YAML root is not a mapping.
    Otherwise delegates to :func:`convert_parsed_to_ecs`.
    """
    try:
        parsed = yaml.safe_load(payload_yaml)
    except yaml.YAMLError:
        return None, ["<yaml-parse-error>"]

    if not isinstance(parsed, dict):
        return None, ["<invalid-root>"]

    return convert_parsed_to_ecs(parsed, mapping)


def sigma_rule_to_catalog_payload(
    rule: dict,
    parsed: dict,
    enabled: bool,
) -> dict:
    """Build the Sekoia Rules Catalog POST body.

    Metadata (name, description, severity, tags, ...) is lifted from the
    parsed Sigma rule dict into structured Sekoia fields; the Sigma
    ``status`` becomes a ``status-<status>`` tag and ``effort`` is the
    fixed ``RULE_EFFORT``. The ``payload`` is the Sigma ``logsource`` block
    (when present) plus the ECS-converted ``detection`` block.

    ``alert_type_uuid`` is auto-derived from the rule's Sigma tags via
    ``derive_alert_type_uuid`` — no user config needed.

    Optional Sekoia fields (``tags``, ``false_positives``) are included
    only when the source Sigma rule actually carries the corresponding
    data.

    The ``enabled`` argument is authoritative only on the POST path (rule
    creation). Callers routing the body through PUT (rule update) MUST
    overwrite ``body["enabled"]`` with the server's current value first,
    otherwise a user who flipped a rule off in the catalog will be
    silently re-enabled on the next sync.
    """
    title = parsed.get("title") or rule.get("name") or rule.get("filename") or "unnamed"
    if len(title) > MAX_NAME_LENGTH:
        title = title[: MAX_NAME_LENGTH - len(_TRUNCATION_MARKER)] + _TRUNCATION_MARKER

    description = parsed.get("description") or rule.get("description") or ""
    # ``references`` is read-only in the Rules Catalog API; keep the Sigma
    # references visible by appending them to the description.
    references = [str(r) for r in parsed.get("references") or [] if r]
    if references:
        description = (description + "\n\nReferences:\n" + "\n".join(f"- {r}" for r in references)).strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[: MAX_DESCRIPTION_LENGTH - len(_TRUNCATION_MARKER)] + _TRUNCATION_MARKER

    level = (parsed.get("level") or rule.get("level") or "").lower()
    severity = SEVERITY_MAP.get(level, DEFAULT_SEVERITY)

    status = str(parsed.get("status") or "").strip().lower()

    # payload = the Sigma ``logsource`` block (when present) and the
    # ECS-converted ``detection`` block, YAML-serialised so it round-trips
    # back to the Sigma shape. Metadata travels in the structured fields.
    payload_doc: dict = {}
    logsource = parsed.get("logsource")
    if isinstance(logsource, dict) and logsource:
        payload_doc["logsource"] = logsource
    payload_doc["detection"] = parsed.get("detection", {})
    payload_yaml = yaml.safe_dump(payload_doc, sort_keys=False, allow_unicode=True)

    # Always attach the integration marker tag so operators can identify
    # rules created by this integration independently of the Sekoia API key
    # that created them (``created_by`` changes on key rotation; a tag does
    # not).
    tags = list(parsed.get("tags") or [])
    if MARKER_TAG not in tags:
        tags.append(MARKER_TAG)
    valhalla_id = rule.get("id")
    if valhalla_id:
        uuid_tag = f"{UUID_TAG_PREFIX}{valhalla_id}"
        if uuid_tag not in tags:
            tags.append(uuid_tag)
    if status:
        status_tag = f"{STATUS_TAG_PREFIX}{status}"
        if status_tag not in tags:
            tags.append(status_tag)

    body: dict = {
        "name": title,
        "type": "sigma",
        "description": description,
        "payload": payload_yaml,
        "severity": severity,
        "effort": RULE_EFFORT,
        "alert_type_uuid": derive_alert_type_uuid(tags),
        "enabled": enabled,
    }

    body["tags"] = tags

    # Sekoia's `datasources` is a list of registered data-source UUIDs in the
    # tenant, not the free-form Sigma `logsource` dict — we have no reliable
    # mapping from `{product, category}` to a tenant-specific UUID, so this
    # field is omitted. `community_uuid` and `related_object_refs` are added
    # by the sync trigger (they need the module config / API lookups).

    falsepositives = parsed.get("falsepositives")
    if falsepositives:
        if isinstance(falsepositives, list):
            body["false_positives"] = "\n".join(str(x) for x in falsepositives)
        else:
            body["false_positives"] = str(falsepositives)

    return body
