# ECS field mappings — the lookup-table half of sigma_mapper.
#
# Kept in its own module so sigma_mapper.py stays scannable: the SigmaHQ
# dicts (majority of the line count) are pure lookup data copied from
# upstream and rarely change in step with the logic.

# ---------------------------------------------------------------------------
# SigmaHQ pySigma-backend-elasticsearch pipelines — source of truth
# ---------------------------------------------------------------------------
# The four dicts below are copied from the ECS pipelines in
# https://github.com/SigmaHQ/pySigma-backend-elasticsearch/tree/main/sigma/pipelines/elasticsearch.
# When SigmaHQ ships an update, mirror the change here rather than
# adding to ``RAW_TO_ECS_CUSTOM``.
#
# The ``.caseless`` suffix that SigmaHQ uses on lowercase-normalised
# multi-fields (``process.executable.caseless``) is preserved literally
# in these source-of-truth dicts and stripped when the runtime map is
# built — Sekoia's engine doesn't expose ``.caseless`` sub-fields.
#
# Fields with SigmaHQ context-aware mappings (Description, Product,
# Company, OriginalFileName, FileVersion, Signature, Initiated,
# Protocol, TargetObject) are intentionally omitted from the static
# dicts here and instead resolved via ``CONTEXT_AWARE_FIELDS`` below.

# From windows.py `ecs_windows()` — static field_mappings.
RAW_TO_ECS_SIGMAHQ_WINDOWS: dict[str, str] = {
    "AccountDomain": "user.domain",
    "AccountName": "user.name",
    "Application": "process.executable.caseless",
    "Archived": "sysmon.file.archived",
    "Channel": "winlog.channel",
    "ClientAddress": "source.ip",
    "ClientName": "source.domain",
    "CommandName": "powershell.command.name",
    "CommandPath": "powershell.command.path",
    "CommandType": "powershell.command.type",
    "ComputerName": "winlog.computer_name",
    "CurrentDirectory": "process.working_directory",
    "DestAddress": "destination.ip",
    "DestPort": "destination.port",
    "Destination": "process.executable.caseless",
    "DestinationHostname": "destination.domain",
    "DestinationIp": "destination.ip",
    "DestinationPort": "destination.port",
    "DestinationPortName": "network.protocol",
    "Device": "file.path",
    "EventID": "event.code",
    "FileName": "file.path",
    "HostApplication": "process.command_line",
    "HostId": "process.entity_id",
    "HostName": "process.title",
    "Image": "process.executable.caseless",
    "ImageLoaded": "file.path",
    "Imphash": "file.pe.imphash",
    "IpAddress": "source.ip",
    "IpPort": "source.port",
    "IsExecutable": "sysmon.file.is_executable",
    "MessageNumber": "powershell.sequence",
    "MessageTotal": "powershell.total",
    "NewEngineState": "powershell.engine.new_state",
    "NewProcessId": "process.pid",
    "NewProcessName": "process.executable.caseless",
    "NewProviderState": "powershell.provider.new_state",
    "ParentCommandLine": "process.parent.command_line",
    "ParentImage": "process.parent.executable.caseless",
    "ParentProcessGuid": "process.parent.entity_id",
    "ParentProcessId": "process.parent.pid",
    "ParentProcessName": "process.parent.name.caseless",
    "Payload": "powershell.file.script_block_text",
    "PipeName": "file.name",
    "PipelineId": "powershell.pipeline_id",
    "PreviousEngineState": "powershell.engine.previous_state",
    "ProcessGuid": "process.entity_id",
    "ProcessId": "process.pid",
    "ProcessName": "process.executable.caseless",
    "ProviderName": "powershell.provider.name",
    "Provider_Name": "winlog.provider_name",
    "QueryName": "dns.question.name",
    "QueryStatus": "sysmon.dns.status",
    "RunspaceId": "powershell.runspace_id",
    "ScriptBlockId": "powershell.file.script_block_id",
    "ScriptBlockText": "powershell.file.script_block_text",
    "ScriptName": "file.path",
    "SequenceNumber": "event.sequence",
    "SignatureStatus": "file.code_signature.status",
    "Signed": "file.code_signature.signed",
    "SourceAddress": "source.ip",
    "SourceHostname": "source.domain",
    "SourceImage": "process.executable.caseless",
    "SourceIp": "source.ip",
    "SourcePort": "source.port",
    "SourceProcessGuid": "process.entity_id",
    "SourceProcessId": "process.pid",
    "SourceThreadId": "process.thread.id",
    # TargetDomainName deviates from SigmaHQ upstream (`user.domain`).
    # Empirically verified 2026-07-17 that Sekoia's Windows and Microsoft
    # Windows parsers extract Security-EventID `TargetDomainName` to
    # `user.target.domain` (alongside `TargetUserName → user.target.name`
    # and `TargetUserSid → user.target.id`), matching the ECS convention
    # for "target user" in logon events. The upstream `user.domain` target
    # doesn't get populated by Sekoia and would silently fail to match.
    "TargetDomainName": "user.target.domain",
    "TargetFilename": "file.path",
    "User": "user.name",
    "WorkstationName": "source.domain",
    # TargetObject omitted here — see CONTEXT_AWARE_FIELDS.
}

# From macos.py `ecs_macos_esf()`.
RAW_TO_ECS_SIGMAHQ_MACOS: dict[str, str] = {
    "CommandLine": "process.command_line",
    "CurrentDirectory": "process.working_directory",
    "DestinationFilename": "file.target.path",
    "DestinationIp": "destination.ip",
    "DestinationPort": "destination.port",
    "EffectiveGroupId": "process.group.id",
    "EffectiveUserId": "process.user.id",
    "FileDirectory": "file.directory",
    "FileName": "file.name",
    "GroupId": "process.group.id",
    "Image": "process.executable.caseless",
    "KextIdentifier": "driver.name",
    "KextPath": "file.path",
    "MemoryProtection": "memory.protection",
    "ParentCommandLine": "process.parent.command_line",
    "ParentImage": "process.parent.executable.caseless",
    "ParentProcessId": "process.parent.pid",
    "ParentProcessName": "process.parent.name.caseless",
    "ProcessId": "process.pid",
    "ProcessName": "process.name.caseless",
    "PtraceRequest": "ptrace.request",
    "RealGroupId": "process.real_group.id",
    "RealUser": "process.real_user.name",
    "RealUserId": "process.real_user.id",
    "SignalNumber": "signal.number",
    "SignatureStatus": "process.code_signature.status",
    "Signed": "process.code_signature.exists",
    "SigningID": "process.code_signature.signing_id",
    "SourceFilename": "file.source.path",
    "SourceImage": "process.executable.caseless",
    "SourceIp": "source.ip",
    "SourcePort": "source.port",
    "SourceProcessId": "process.pid",
    "TargetFilename": "file.path",
    "TargetGroup": "group.target.name",
    "TargetGroupId": "group.target.id",
    "TargetImage": "target.process.executable.caseless",
    "TargetProcessGUID": "target.process.entity_id",
    "TargetProcessId": "target.process.pid",
    "TargetProcessName": "target.process.name.caseless",
    "TargetUser": "user.target.name",
    "TargetUserId": "user.target.id",
    "TeamID": "process.code_signature.team_id",
    "User": "process.user.name",
    "UserId": "process.user.id",
    "XpcServiceName": "xpc.service_name",
}

# From zeek.py `ecs_zeek_beats()`. Only literal, non-wildcard targets
# survive — SigmaHQ's `zeek.*.arg` wildcard patterns aren't usable as
# Sekoia ECS field names. List-of-target entries collapse to the last
# item (usually the most ECS-canonical).
RAW_TO_ECS_SIGMAHQ_ZEEK: dict[str, str] = {
    "TTLs": "dns.answers.ttl",
    "agent.version": "version",
    "answer": "dns.answers.name",
    "answers": "dns.answers.name",
    "c-cookie": "http.cookie_vars",
    "c-ip": "source.ip",
    "c-uri": "url.original",
    "c-uri-extension": "url.extension",
    "c-uri-query": "url.query",
    "c-uri-stem": "url.original",
    "c-useragent": "user_agent.original",
    "clientIP": "source.ip",
    "clientip": "source.ip",
    "cs-bytes": "http.request.body.bytes",
    "cs-cookie": "http.cookie_vars",
    "cs-host": "destination.domain",
    "cs-method": "http.request.method",
    "cs-referer": "http.request.referrer",
    "cs-version": "http.version",
    "cyu": "gquic.cyu",
    "cyutags": "gquic.cyutags",
    "dest_domain": "server_name",
    "dest_ip": "destination.ip",
    "dest_port": "destination.port",
    "dst": "destination.ip",
    "dst_ip": "destination.ip",
    "dst_port": "destination.port",
    "duration": "event.duration",
    "failure_reason": "dpd.failure_reason",
    "fc_reply": "dnp3.function.reply",
    "fc_request": "dnp3.function.request",
    "http_method": "http.request.method",
    "http_user_agent": "user_agent.original",
    "http_version": "http.version",
    "iin": "dnp3.inn",
    "method": "http.request.method",
    "mqtt_action": "smb.action",
    "network_application": "network.protocol",
    "network_community_id": "network.community_id",
    "network_protocol": "network.transport",
    "orig_bytes": "source.bytes",
    "orig_cc": "source.geo.country_iso_code",
    "orig_l2_addr": "source.mac",
    "orig_pkts": "source.packets",
    "p": "destination.port",
    "packet_segment": "dpd.packet_segment",
    "parent_domain": "dns.question.registered_domain",
    "proto": "network.transport",
    "qclass_name": "dns.question.class",
    "qtype_name": "dns.question.type",
    "query": "dns.question.name",
    "question_length": "labels.dns.query_length",
    "r-dns": "destination.domain",
    "rcode_name": "dns.response_code",
    "record_type": "dns.question.type",
    "referrer": "http.request.referrer",
    "request_body_len": "http.request.body.bytes",
    "resp_bytes": "destination.bytes",
    "resp_cc": "destination.geo.country_iso_code",
    "resp_l2_addr": "destination.mac",
    "resp_pkts": "destination.packets",
    "response_body_len": "http.response.body.bytes",
    "rtt": "event.duration",
    "sc-bytes": "http.response.body.bytes",
    "sc-status": "http.response.status_code",
    "server_addr": "destination.ip",
    "smb_action": "smb.action",
    "src": "source.ip",
    "src_ip": "source.ip",
    "src_port": "source.port",
    "status_code": "http.response.status_code",
    "trans_id": "dns.id",
    "tunnel_action": "tunnel.action",
    "uri": "url.original",
}

# SigmaHQ's kubernetes.py pipeline was removed on 2026-07-16 after
# verifying against SEKOIA-IO/intake-formats Kubernetes/audit-log/ingest/parser.yml
# that every one of its targets was symbolic. Sekoia's K8s audit parser
# emits flat `kubernetes.*` fields (e.g. `kubernetes.object.name`,
# `kubernetes.namespace`, `kubernetes.resource`, `kubernetes.api.group`,
# `kubernetes.subresource`) plus `event.action` for `verb` and `user.name`
# for `user.username` — none of the SigmaHQ `kubernetes.audit.*` targets
# are ever produced. Corrected entries live in `RAW_TO_ECS_CUSTOM`.
# Deep-nested SigmaHQ targets (`capabilities`, `hostPath`, `privileged`,
# which pointed at `kubernetes.audit.requestObject.spec...*`) have no
# ECS equivalent in Sekoia's parser and are simply dropped — rules using
# them will fall through to the honest ``skipped_unmapped`` counter.

# ---------------------------------------------------------------------------
# Custom mappings — fields SigmaHQ's pipelines don't cover
# ---------------------------------------------------------------------------
# These are ours (bespoke), covering cloud/audit taxonomies pySigma
# doesn't include. If SigmaHQ later adds any of these, delete from here
# to keep the SigmaHQ dicts as the single source of truth.
RAW_TO_ECS_CUSTOM: dict[str, str] = {
    # AWS CloudTrail
    "eventName": "event.action",
    "eventSource": "event.provider",
    "operationName": "event.action",
    "OperationName": "event.action",  # PascalCase variant seen in some rules
    "eventType": "event.action",  # CloudTrail eventType
    "EventType": "event.action",  # PascalCase variant
    # Sekoia's aws-cloudtrail parser writes `errorCode` to `event.code`
    # (verified 2026-07-16 against SEKOIA-IO/intake-formats
    # AWS/aws-cloudtrail/ingest/parser.yml).
    "errorCode": "event.code",
    # ``requestParameters.*`` fields aren't mapped. Sekoia's aws-cloudtrail
    # parser stores the whole ``requestParameters`` object as a JSON blob
    # at ``aws.cloudtrail.flattened.request_parameters`` (verified against
    # SEKOIA-IO/intake-formats AWS/aws-cloudtrail/ingest/parser.yml) rather
    # than expanding subfields, so a flat ECS mapping would be symbolic.
    # A JSON-blob substring-match transform was considered but dropped —
    # only 4 rules in the ~3.6k Valhalla feed reference ``requestParameters.*``
    # (2 of which have shapes a transform could handle). Not worth the code
    # for the yield.
    # Azure sign-in logs — Sekoia's Azure/azure-ad parser exposes sign-in
    # events under the `azuread.properties.*` namespace (camelCase),
    # verified 2026-07-16 against SEKOIA-IO/intake-formats
    # Azure/azure-ad/ingest/parser.yml.
    "riskEventType": "azuread.properties.riskEventType",
    "AuthenticationRequirement": "azuread.properties.authenticationRequirement",
    # Dropped:
    #   `ResultType` — Sekoia's Azure AD parser doesn't emit this field
    #     (uses action.outcome/action.outcome_reason instead). Symbolic.
    #   `properties.message` — Azure activity-logs parser doesn't map it.
    #   `auditType.action` / `auditType.category` — used only by Bitbucket
    #     Sigma rules; Sekoia has no Bitbucket intake format at all, so
    #     any mapping would be symbolic.
    # Linux auditd — additional syscall args + core fields
    "SYSCALL": "auditd.data.syscall",
    "type": "auditd.log.record_type",
    "a0": "auditd.data.a0",
    "a1": "auditd.data.a1",
    "a2": "auditd.data.a2",
    "a3": "auditd.data.a3",
    "a4": "auditd.data.a4",
    "exe": "process.executable",
    "cfgpath": "auditd.data.cfgpath",
    # W3C ELF server-side URI fields. SigmaHQ Zeek covers only the
    # client-side variants (``c-uri``, ``c-uri-stem``); the ``cs-`` prefix
    # (server-log format) is common in IIS/proxy Sigma rules.
    "cs-uri": "url.original",
    "cs-uri-query": "url.query",
    "cs-uri-stem": "url.original",
    # W3C ELF variant (server-side ``userAgent`` camelCase — not
    # covered by Zeek, which uses ``http_user_agent``/``c-useragent``).
    "userAgent": "user_agent.original",
    # ``cs-user-agent`` is the hyphenated W3C ELF form used in some
    # IIS/proxy Sigma rules (e.g. exploit-webserver-* category); SigmaHQ
    # Zeek maps only the abbreviated ``c-useragent``.
    "cs-user-agent": "user_agent.original",
    # ``user_agent`` (bare) shows up in Zeek HTTP Sigma rules; SigmaHQ
    # Zeek maps the equivalent ``http_user_agent`` but not this variant.
    "user_agent": "user_agent.original",
    # Zeek file/TLS fingerprint fields — replace the SigmaHQ Zeek pipeline's
    # symbolic ``zeek.files.*`` / ``zeek.ssl.*`` targets with the flat ECS
    # forms Sekoia's Corelight parser actually emits (verified 2026-07-16
    # against SEKOIA-IO/intake-formats Corelight/corelight/ingest/parser.yml).
    "md5": "file.hash.md5",
    "sha1": "file.hash.sha1",
    "sha256": "file.hash.sha256",
    "mime_type": "file.mime_type",
    "ja3": "tls.client.ja3",
    "ja3s": "tls.server.ja3s",
    # Kubernetes audit — both the dotted ``objectRef.*`` form (as Sigma
    # rules often write) and the bare short names (from SigmaHQ's
    # kubernetes pipeline, which we no longer mirror because its targets
    # were symbolic). Targets verified 2026-07-16 against
    # SEKOIA-IO/intake-formats Kubernetes/audit-log/ingest/parser.yml:
    # Sekoia's parser emits flat ``kubernetes.*`` fields plus
    # ``event.action`` for `verb` and ``user.name`` for `user.username`.
    "objectRef.name": "kubernetes.object.name",
    "objectRef.namespace": "kubernetes.namespace",
    "objectRef.resource": "kubernetes.resource",
    "objectRef.apiGroup": "kubernetes.api.group",
    "objectRef.subresource": "kubernetes.subresource",
    "apiGroup": "kubernetes.api.group",
    "verb": "event.action",
    # Dropped (no ECS equivalent in Sekoia's parser — deep-nested paths
    # like ``kubernetes.audit.requestObject.spec...`` are not exposed):
    # ``capabilities``, ``hostPath``, ``privileged``. Rules using them
    # will fall through to the honest ``skipped_unmapped`` counter.
    # ``namespace``, ``resource``, ``subresource``, ``username`` (bare
    # names) are also intentionally not mapped — they're context-ambiguous
    # across logsources, and no rules in the current feed use them without
    # the ``objectRef.`` prefix.
    # Note: QueryName is intentionally NOT here — SigmaHQ Windows
    # already maps it (dns.question.name).
}


# ---------------------------------------------------------------------------
# Windows overrides — verified against Sekoia's Windows parser
# ---------------------------------------------------------------------------
# These win over the SigmaHQ Windows map. Verified against the
# SEKOIA-IO/intake-formats ``Windows/windows`` parser and its Sysmon test
# fixtures (sysmon_6, sysmon_7, sysmon_10): the parser keeps the access
# *source* in ``process.*`` and leaves the target process and the
# signature fields under ``action.properties.*``.
RAW_TO_ECS_WINDOWS_OVERRIDES: dict[str, str] = {
    # ProcessAccess (Sysmon 10): ``process.executable`` is the SourceImage.
    "TargetImage": "action.properties.TargetImage",
    "TargetProcessId": "action.properties.TargetProcessId",
    "TargetProcessGUID": "action.properties.TargetProcessGUID",
    # ImageLoad / DriverLoad (Sysmon 6/7): no ``*.code_signature.*`` fields.
    "Signature": "action.properties.Signature",
    "Signed": "action.properties.Signed",
    "SignatureStatus": "action.properties.SignatureStatus",
}

# ---------------------------------------------------------------------------
# Windows-only gap fillers (applied after the SigmaHQ Windows map)
# ---------------------------------------------------------------------------
# Gated on ``logsource.product: windows``: generic names such as ``Status``
# or ``Path`` would otherwise be accepted for e.g. Okta rules, where they
# never match.
RAW_TO_ECS_CUSTOM_WINDOWS: dict[str, str] = {
    # Windows Security event_data — Sekoia's Winlogbeat/Windows parsers
    # route arbitrary event_data.<X> subfields to `action.properties.<X>`,
    # verified 2026-07-17 by pushing a synthetic Winlogbeat event to a
    # USA1 tenant with `winlog.event_data.AccessMask=0xDEADBEEF` and
    # confirming the value was queryable at `action.properties.AccessMask`
    # (and NOT at `winlog.event_data.AccessMask`). Same test verified
    # `action.properties.ObjectName` and `action.properties.ProcessName`.
    # Every SigmaHQ Windows Sigma rule field that isn't extracted into a
    # named ECS position lands under this prefix.
    "AccessList": "action.properties.AccessList",
    "AccessMask": "action.properties.AccessMask",
    "AttributeLDAPDisplayName": "action.properties.AttributeLDAPDisplayName",
    "AttributeValue": "action.properties.AttributeValue",
    "AuthenticationPackageName": "action.properties.AuthenticationPackageName",
    "CallTrace": "action.properties.CallTrace",
    "Category": "action.properties.Category",
    "Configuration": "action.properties.Configuration",
    "Contents": "action.properties.Contents",
    "ContextInfo": "action.properties.ContextInfo",
    "Data": "action.properties.Data",
    "Details": "action.properties.Details",
    "FilterName": "action.properties.FilterName",
    "GrantedAccess": "action.properties.GrantedAccess",
    "InterfaceUuid": "action.properties.InterfaceUuid",
    "IsatapRouter": "action.properties.IsatapRouter",
    "Level": "action.properties.Level",
    "LogonId": "action.properties.LogonId",
    "LogonProcessName": "action.properties.LogonProcessName",
    "LogonType": "action.properties.LogonType",
    "ModifyingApplication": "action.properties.ModifyingApplication",
    "NewValue": "action.properties.NewValue",
    "ObjectClass": "action.properties.ObjectClass",
    "ObjectDN": "action.properties.ObjectDN",
    "ObjectName": "action.properties.ObjectName",
    "ObjectServer": "action.properties.ObjectServer",
    "ObjectType": "action.properties.ObjectType",
    "ObjectValueName": "action.properties.ObjectValueName",
    "OpNum": "action.properties.OpNum",
    "Path": "action.properties.Path",
    "PrivilegeList": "action.properties.PrivilegeList",
    "RelativeTargetName": "action.properties.RelativeTargetName",
    "SamAccountName": "action.properties.SamAccountName",
    "ShareName": "action.properties.ShareName",
    "SourceName": "action.properties.SourceName",
    "Status": "action.properties.Status",
    "SubjectUserSid": "action.properties.SubjectUserSid",
    "TargetName": "action.properties.TargetName",
    "TaskContent": "action.properties.TaskContent",
    "TaskName": "action.properties.TaskName",
    "TicketEncryptionType": "action.properties.TicketEncryptionType",
    # Users (Sigma canonical → ECS user.*). All three verified 2026-07-17
    # against Sekoia's Microsoft Windows parser (Security EventID 4624).
    "SubjectUserName": "user.name",
    "TargetUserName": "user.target.name",
    "TargetUserSid": "user.target.id",
    # Windows event metadata variants
    "EventLog": "winlog.channel",
    # Sysmon fields not in SigmaHQ's static Windows map
    "IntegrityLevel": "process.integrity_level",
    "ImagePath": "process.executable",
    "ServiceName": "service.name",
    "ServiceFileName": "service.executable",
}


def _strip_caseless(target: str) -> str:
    """Sekoia's ECS schema doesn't advertise ``.caseless`` sub-fields;
    ship the base ECS target instead."""
    return target[:-9] if target.endswith(".caseless") else target


def _merge(*pipelines: dict[str, str]) -> dict[str, str]:
    """Merge with ``setdefault`` — the first map to define a source field
    wins. ``.caseless`` targets are stripped since Sekoia's ECS schema
    doesn't expose those sub-fields."""
    merged: dict[str, str] = {}
    for pipeline in pipelines:
        for src, target in pipeline.items():
            merged.setdefault(src, _strip_caseless(target))
    return merged


# Runtime maps used by the converter, selected by ``logsource.product``.
# Do not edit — edit the source dicts.
#
# Every map starts with its own product's SigmaHQ map, so shared names
# resolve the way that product's parser emits them (macOS ``ProcessName`` →
# ``process.name``, not the Windows ``process.executable``). The other
# SigmaHQ maps follow as gap fillers for generic names: SigmaHQ's Windows
# map, for instance, has no ``CommandLine`` entry.
#
# The Windows-only ``event_data`` catch-alls (``Status``, ``Path``, …) and
# the parser-verified Windows overrides are only part of the Windows map.
RAW_TO_ECS_BY_PRODUCT: dict[str, dict[str, str]] = {
    "windows": _merge(
        RAW_TO_ECS_WINDOWS_OVERRIDES,
        RAW_TO_ECS_SIGMAHQ_WINDOWS,
        RAW_TO_ECS_CUSTOM_WINDOWS,
        RAW_TO_ECS_CUSTOM,
        RAW_TO_ECS_SIGMAHQ_MACOS,
        RAW_TO_ECS_SIGMAHQ_ZEEK,
    ),
    "macos": _merge(
        RAW_TO_ECS_SIGMAHQ_MACOS,
        RAW_TO_ECS_CUSTOM,
        RAW_TO_ECS_SIGMAHQ_WINDOWS,
        RAW_TO_ECS_SIGMAHQ_ZEEK,
    ),
    "zeek": _merge(
        RAW_TO_ECS_SIGMAHQ_ZEEK,
        RAW_TO_ECS_CUSTOM,
        RAW_TO_ECS_SIGMAHQ_WINDOWS,
        RAW_TO_ECS_SIGMAHQ_MACOS,
    ),
}
# Fallback for every other product (linux, cloud, web, none).
RAW_TO_ECS: dict[str, str] = _merge(
    RAW_TO_ECS_SIGMAHQ_WINDOWS,
    RAW_TO_ECS_CUSTOM,
    RAW_TO_ECS_SIGMAHQ_MACOS,
    RAW_TO_ECS_SIGMAHQ_ZEEK,
)


# Products whose events reach Sekoia through the Windows event-log parser
# (RPC Firewall writes to a Windows event channel), so they share the
# Windows map and its ``action.properties.*`` catch-alls.
_PRODUCT_ALIASES: dict[str, str] = {"rpc_firewall": "windows"}


def mapping_for_product(product: str | None) -> dict[str, str]:
    """Field map for a Sigma ``logsource.product`` (case-insensitive);
    :data:`RAW_TO_ECS` for unknown or missing products."""
    if not isinstance(product, str):
        return RAW_TO_ECS
    key = product.strip().lower()
    return RAW_TO_ECS_BY_PRODUCT.get(_PRODUCT_ALIASES.get(key, key), RAW_TO_ECS)


# ---------------------------------------------------------------------------
# Context-aware fields
# ---------------------------------------------------------------------------
# Fields whose ECS target depends on the Sigma rule's
# ``logsource.category``. Consulted BEFORE ``RAW_TO_ECS``. If the
# category isn't listed for a field, the rule is treated as unmapped
# (skipped) — matching SigmaHQ's conditional-mapping behaviour.
#
# The PE-metadata fields (Description, Product, Company, OriginalFileName,
# FileVersion) and Signature/Initiated/Protocol come from
# ``ecs_windows_variable_mappings`` in windows.py. TargetObject is our
# original bespoke context-aware branch (Sigma convention).
# Sysmon fields whose target depends on the event type. Verified against
# the Sekoia Windows parser fixtures (sysmon_1/6/7): PE metadata stays in
# ``action.properties.*``; the loaded image is ``dll.path`` for ImageLoad
# but ``process.executable`` for DriverLoad.
_PE_METADATA_CATEGORIES = ("process_creation", "image_load")

CONTEXT_AWARE_FIELDS: dict[str, dict[str, str]] = {
    # Bespoke — Sigma convention rather than pySigma.
    "TargetObject": {
        "registry_set": "registry.path",
        "registry_add": "registry.path",
        "registry_delete": "registry.path",
        "registry_rename": "registry.path",
        "registry_event": "registry.path",
        "file_event": "file.path",
    },
    **{
        field: {category: f"action.properties.{field}" for category in _PE_METADATA_CATEGORIES}
        for field in ("FileVersion", "Description", "Product", "Company", "OriginalFileName")
    },
    "ImageLoaded": {
        "image_load": "dll.path",
        "driver_load": "process.executable",
    },
    "Imphash": {
        "process_creation": "process.pe.imphash",
        "driver_load": "process.pe.imphash",
        "image_load": "dll.pe.imphash",
    },
    "Protocol": {
        "network_connection": "network.transport",
    },
    # ``Initiated`` is intentionally absent: the parser doesn't emit it
    # (SigmaHQ's ``network.direction`` target holds ingress/egress, never
    # ``'true'``), so rules using it are reported as unmapped.
}
CONTEXT_AWARE_FIELDS["Description"]["sysmon_error"] = "action.properties.Description"

# Targets of the ``Hashes`` transform, by ``logsource.category``. The
# parser fills ``process.hash.*`` for process events, ``dll.hash.*`` for
# ImageLoad and ``file.hash.*`` for the file-hash events (Sysmon 15/23/26);
# SHA1 only exists for process events, SHA512 nowhere.
HASH_TARGETS_DEFAULT: dict[str, str] = {
    "md5": "process.hash.md5",
    "sha1": "process.hash.sha1",
    "sha256": "process.hash.sha256",
    "imphash": "process.pe.imphash",
}
_FILE_HASH_TARGETS: dict[str, str] = {
    "md5": "file.hash.md5",
    "sha256": "file.hash.sha256",
    "imphash": "file.pe.imphash",
}
HASH_TARGETS_BY_CATEGORY: dict[str, dict[str, str]] = {
    "image_load": {
        "md5": "dll.hash.md5",
        "sha256": "dll.hash.sha256",
        "imphash": "dll.pe.imphash",
    },
    "create_stream_hash": _FILE_HASH_TARGETS,
    "file_delete": _FILE_HASH_TARGETS,
    "file_delete_detected": _FILE_HASH_TARGETS,
}

# Fields produced by our own Stage 2 transforms (Hashes value split,
# context-aware rewrites) that are already ECS-shaped and must pass
# through the walker untouched. Also includes a handful of already-ECS
# field names some Sigma rules use directly (e.g. GCP audit fields).
_ECS_PASSTHROUGH_FIELDS: frozenset[str] = frozenset(
    {
        *HASH_TARGETS_DEFAULT.values(),
        *(t for targets in HASH_TARGETS_BY_CATEGORY.values() for t in targets.values()),
        "registry.path",
        "file.path",
        # GCP audit — Sigma rules already write these in ECS form.
        "gcp.audit.method_name",
        "gcp.audit.authentication_info.principal_email",
        "gcp.audit.authorization_info.permission",
        "gcp.audit.resource_name",
    }
)
