## Additional configuration for TEHTRIS EDR syslog mode

This document describes the changes introduced for TEHTRIS EDR in intake-formats branch `Imp/Tehtris_support_syslog_connection`.

## What changed

1. The parser now supports TEHTRIS EDR events received through a syslog envelope.
2. A dedicated extraction step is executed before JSON parsing to isolate the JSON payload.
3. Backward compatibility is preserved: if the syslog envelope is not detected, the parser still reads `original.message` directly.
4. A new test case was added to validate syslog ingestion.

## Supported input formats

The parser now accepts both formats below.

### 1. JSON payload only (existing behavior)

`original.message` contains a JSON object.

### 2. Syslog + JSON payload (new behavior)

`original.message` contains a RFC5424-like syslog header followed by a JSON payload, for example:

```text
<14>1 2025-10-27T12:34:56.789Z myhost app 1234 LOG [SEKOIA@53288 intake_key="xxxxxxxxxxxxxxxxxxx"] {"id":"123","uuid__":"abc","time":"2025-10-27T12:35:00.000Z","description":"Application policy: test ([I] T1234 test)"}
```

## Syslog requirements

To ensure proper parsing, keep the following elements in the syslog message:

1. A standard syslog prefix (`<PRI>VERSION TIMESTAMP HOST APP PROCID`).
2. The literal token `LOG` after `PROCID`.
3. Structured data including `SEKOIA@53288` and `intake_key`, for example:
   `[SEKOIA@53288 intake_key="<your_intake_key>"]`
4. The original TEHTRIS EDR JSON event appended after the structured data.

If this syslog pattern does not match, parsing automatically falls back to direct JSON parsing from `original.message`.

## Validation coverage

The branch adds `tests/test_syslog.json` in intake-formats for TEHTRIS EDR.
This test validates extraction from the syslog envelope and normal event mapping (`@timestamp`, `agent.id`, `event.reason`, MITRE technique fields, etc.).