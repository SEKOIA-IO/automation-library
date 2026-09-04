import re
from typing import Optional

import yaml

from nextron_valhalla_sigma_rules_modules.ecs_field_maps import (
    CONTEXT_AWARE_FIELDS,
    RAW_TO_ECS,
    _ECS_PASSTHROUGH_FIELDS,
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

# Sekoia ``effort`` is derived from Sigma's rule maturity (``status`` field).
# Lower effort = higher maturity. Also used by the sync trigger to filter
# rules by minimum maturity: a rule passes when its effort is ``<=`` the
# effort configured for ``min_sigma_status``.
STATUS_EFFORT_MAP = {
    "stable": 1,
    "test": 2,
    "experimental": 3,
    "unsupported": 4,
    "deprecated": 4,
}
# Returned when the Sigma rule has no ``status`` field.
DEFAULT_EFFORT = 3

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

# Sekoia alert-type UUIDs are stable across tenants (Ecsirt-standard
# taxonomy). We derive an ``alert_type_uuid`` per rule from its Sigma
# MITRE tactic tags rather than requiring a user-supplied config value.
DEFAULT_ALERT_UUID = "599f4b1a-dd60-43fe-8ee9-07d3c5d00ded"  # application-compromise

# Priority-ordered list: first matching tag wins. Later kill-chain
# stages beat earlier ones; specific detections (c&c, exfiltration)
# beat generic categories.
TAG_ALERT_UUID_MAP: tuple[tuple[str, str], ...] = (
    ("attack.exfiltration",        "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"),  # exfiltration
    ("attack.command-and-control", "47e51ab7-4caa-4c4b-8442-a1caf868806d"),  # c&c
    ("attack.persistence",         "5928d144-2038-4a87-b996-b3585a9a1a41"),  # backdoor
    ("attack.initial-access",      "4321cd89-89d6-4674-9e99-690ce0e61621"),  # exploit
    ("attack.discovery",           "38305ebd-cec9-47ff-b38b-d20bd22eb79d"),  # appscan
    ("attack.reconnaissance",      "38305ebd-cec9-47ff-b38b-d20bd22eb79d"),  # appscan
)


def derive_alert_type_uuid(tags: list) -> str:
    """Return the highest-priority alert_type_uuid the Sigma tags map
    to, or ``DEFAULT_ALERT_UUID`` if no tactic tag matches."""
    tag_set = {t.lower() for t in tags if isinstance(t, str)}
    for tag, uuid in TAG_ALERT_UUID_MAP:
        if tag in tag_set:
            return uuid
    return DEFAULT_ALERT_UUID


# Sigma Hashes values look like ``ALGO=DIGEST``; recognised algorithms are
# folded to their ECS ``process.hash.<algo>`` counterpart.
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
    logsource_category: Optional[str],
) -> Optional[str]:
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


def _parse_hash_values(value) -> Optional[list[tuple[str, str]]]:
    """Parse a Sigma ``Hashes`` value into ``[(algo_lower, digest), ...]``.

    Accepts either a single string like ``"MD5=abc,SHA256=def"`` or a list of
    such strings. Returns ``None`` if any value doesn't match ``ALGO=DIGEST``
    or the algo is unknown — signals the caller to skip the rule.
    """
    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, list):
        candidates: list = []
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


def _apply_hashes_transform(selection_dict: dict) -> Optional[dict]:
    """Rewrite a selection dict's ``Hashes|<mods>`` key into individual
    ``process.hash.<algo>|<mods>`` keys.

    Semantics note: if the original value is a list of mixed algos (e.g.
    ``[MD5=x, SHA256=y]``), Sigma treats them as OR-matched under the same
    key. This transform emits them as AND-matched sibling keys within the
    same dict, which is a known approximation.

    Two cases where the approximation stays exact and covers the entire
    Valhalla feed in practice:

    1. Single-algo lists (e.g. ``[MD5=x, MD5=y]``) — values collapse back
       into a same-key list, so OR is preserved.
    2. Multi-algo IOC lists that enumerate malicious files by fingerprint
       (e.g. ``[SHA256=A, SHA1=B, MD5=C, SHA256=D, SHA1=E, MD5=F]``, one
       set of hashes per file). A real event has exactly one digest per
       algo, so the AND across sibling algo keys is satisfied iff the
       event's file matches one of the listed fingerprints — which is the
       intended OR-over-files semantic. Valhalla's Hashes rules are all
       of this shape.

    The approximation would only misbehave for lists of *orphan* hashes
    (unrelated files, one algo each), which don't occur in Valhalla-authored
    IOC rules.

    Returns:
        - The updated dict on success.
        - ``None`` if the ``Hashes`` value is malformed (caller marks rule
          as unmapped and skips it).
        - The input dict unchanged if no ``Hashes*`` key is present.
    """
    hashes_key = None
    for k in selection_dict.keys():
        if isinstance(k, str) and (k == "Hashes" or k.startswith("Hashes|")):
            hashes_key = k
            break
    if hashes_key is None:
        return selection_dict

    _, mods = _split_field_key(hashes_key)
    parsed = _parse_hash_values(selection_dict[hashes_key])
    if parsed is None:
        return None

    # Group digests by algo so lists collapse into a single ECS key.
    by_algo: dict[str, list[str]] = {}
    for algo, digest in parsed:
        by_algo.setdefault(algo, []).append(digest)

    new_dict: dict = {k: v for k, v in selection_dict.items() if k != hashes_key}
    for algo, digests in by_algo.items():
        key = f"process.hash.{algo}{mods}"
        new_dict[key] = digests[0] if len(digests) == 1 else digests
    return new_dict


def _convert_selection(
    node,
    mapping: dict[str, str],
    unmapped: list[str],
    logsource_category: Optional[str] = None,
):
    """Recurse into a detection selection block or list of such blocks.

    Applies the Hashes value transform (Stage 2), then rewrites field-name
    keys via ``mapping`` while preserving Sigma modifiers. Context-dependent
    fields (currently ``TargetObject``) resolve against ``logsource_category``.
    Any bare field not resolvable is appended to ``unmapped``; the key is
    kept as-is (the caller decides to skip the rule).
    """
    if isinstance(node, dict):
        transformed = _apply_hashes_transform(node)
        if transformed is None:
            unmapped.append("Hashes")
            transformed = node  # keep going so we still surface other unmapped fields

        new_dict: dict = {}
        for k, v in transformed.items():
            if isinstance(k, str):
                bare, mods = _split_field_key(k)
                if not bare:
                    # Bare-modifier key like ``|all`` — Sigma keyword-
                    # modifier construct with no field name. Preserve.
                    new_dict[k] = _convert_selection(
                        v, mapping, unmapped, logsource_category
                    )
                    continue
                mapped = _resolve_field(bare, mapping, logsource_category)
                if mapped is None:
                    unmapped.append(bare)
                    new_key = k
                else:
                    new_key = f"{mapped}{mods}"
                new_dict[new_key] = _convert_selection(
                    v, mapping, unmapped, logsource_category
                )
            else:
                new_dict[k] = _convert_selection(
                    v, mapping, unmapped, logsource_category
                )
        return new_dict
    if isinstance(node, list):
        return [
            _convert_selection(item, mapping, unmapped, logsource_category)
            for item in node
        ]
    return node


def convert_parsed_to_ecs(
    parsed: dict,
    mapping: Optional[dict[str, str]] = None,
) -> tuple[Optional[dict], list[str]]:
    """ECS-convert the ``detection`` block of an already-parsed Sigma rule.

    Only ``parsed["detection"]`` is transformed. Every other field
    (``title``, ``description``, ``level``, ``status``, ``tags``,
    ``logsource``, ``falsepositives``, ``related``, ...) is left unchanged
    so the caller can lift them into structured Sekoia body fields.

    Args:
        parsed: The parsed Sigma rule dict.
        mapping: Field-name mapping to use. Defaults to :data:`RAW_TO_ECS`.

    Returns:
        ``(parsed_rule_dict, [])`` if every field in every selection block
        is resolvable, otherwise ``(None, [unique_unmapped_field_names])``.
        The unmapped list is de-duplicated and sorted for stable output.

        On missing/malformed detection block returns
        ``(None, ["<no-detection>"])``.
    """
    if mapping is None:
        mapping = RAW_TO_ECS

    detection = parsed.get("detection")
    if not isinstance(detection, dict):
        return None, ["<no-detection>"]

    logsource = parsed.get("logsource") or {}
    category = logsource.get("category") if isinstance(logsource, dict) else None

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
    mapping: Optional[dict[str, str]] = None,
) -> tuple[Optional[dict], list[str]]:
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

    Metadata (name, description, severity, effort, tags, ...) is lifted
    from the parsed Sigma rule dict into structured Sekoia fields. The
    ``payload`` is only the ECS-converted ``detection:`` block,
    YAML-serialised with the ``detection:`` keyword preserved.

    ``alert_type_uuid`` is auto-derived from the rule's Sigma tags via
    ``derive_alert_type_uuid`` — no user config needed.

    Optional Sekoia fields (``tags``, ``false_positives``) are included
    only when the source Sigma rule actually carries the corresponding
    data.
    """
    title = parsed.get("title") or rule.get("name") or rule.get("filename") or "unnamed"
    if len(title) > MAX_NAME_LENGTH:
        title = title[: MAX_NAME_LENGTH - len(_TRUNCATION_MARKER)] + _TRUNCATION_MARKER

    description = parsed.get("description") or rule.get("description") or ""
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = (
            description[: MAX_DESCRIPTION_LENGTH - len(_TRUNCATION_MARKER)]
            + _TRUNCATION_MARKER
        )

    level = (parsed.get("level") or rule.get("level") or "").lower()
    severity = SEVERITY_MAP.get(level, DEFAULT_SEVERITY)

    status = (parsed.get("status") or "").lower()
    effort = STATUS_EFFORT_MAP.get(status, DEFAULT_EFFORT)

    # payload = only the detection block, YAML-serialised with the
    # ``detection:`` key so it round-trips back to the Sigma detection shape.
    detection_only = {"detection": parsed.get("detection", {})}
    payload_yaml = yaml.safe_dump(
        detection_only, sort_keys=False, allow_unicode=True
    )

    # Always attach the integration marker tag so operators can identify
    # rules created by this integration independently of the Sekoia API key
    # that created them (``created_by`` changes on key rotation; a tag does
    # not).
    tags = list(parsed.get("tags") or [])
    if MARKER_TAG not in tags:
        tags.append(MARKER_TAG)

    body: dict = {
        "name": title,
        "type": "sigma",
        "description": description,
        "payload": payload_yaml,
        "severity": severity,
        "effort": effort,
        "alert_type_uuid": derive_alert_type_uuid(tags),
        "enabled": enabled,
    }

    # Optional fields — include only when the Sigma rule actually has them.
    # community_uuid is deliberately not shipped (see docstring).
    body["tags"] = tags

    # Sekoia's `datasources` is a list of registered data-source UUIDs in the
    # tenant, not the free-form Sigma `logsource` dict — we have no reliable
    # mapping from `{product, category}` to a tenant-specific UUID, so this
    # field is omitted. The Sigma logsource stays visible via the payload
    # YAML if needed downstream.

    # `related_object_refs` is deliberately not shipped (see docstring).

    falsepositives = parsed.get("falsepositives")
    if falsepositives:
        if isinstance(falsepositives, list):
            body["false_positives"] = "\n".join(str(x) for x in falsepositives)
        else:
            body["false_positives"] = str(falsepositives)

    return body
