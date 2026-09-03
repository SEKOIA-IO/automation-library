# Slack Audit Logs

Sekoia automation module collecting audit events from the
[Slack Audit Logs API](https://docs.slack.dev/admins/audit-logs-api/) and forwarding them to a
Sekoia intake.

## Requirements

- Slack Enterprise Grid — the Audit Logs API does not exist on other plans
- A Slack **user** token (`xoxp-…`) with the `auditlogs:read` scope, from an app installed on the
  **organization**, not on a workspace

## Module configuration

| Setting | Default | Description |
| --- | --- | --- |
| `token` | — | Slack user token, secret |
| `base_url` | `https://api.slack.com/audit/v1` | Base URL of the Slack Audit Logs API |

Use the console's credentials test to validate the token: it distinguishes a rejected token from a
plan restriction from an API outage.

## Connector configuration

| Setting | Default | Range | Description |
| --- | --- | --- | --- |
| `intake_key` | — | required | Sekoia intake receiving the events |
| `intake_server` | — | — | Leave empty to use the platform intake URL |
| `frequency` | 60 | 10–3600 | Minimum seconds between collection cycles |
| `limit` | 1000 | 1–9999 | Events per API page. The knob for catching up on a backlog |
| `ratelimit_per_minute` | 30 | 1–50 | Slack's quota is **organization-wide**, shared with every other Slack app |
| `timebuffer` | 60 | 1–3600 | Events younger than this are left for the next cycle, covering Slack's indexing lag |
| `lookback_seconds` | 3600 | ≥ 60 | Depth of the first run. Only applies when no state exists |
| `excluded_actions` | — | — | Slack actions to drop instead of forwarding. An action added here is not collected from then on and cannot be recovered without re-collecting the period |

## How collection works

Slack returns `/audit/v1/logs` newest-first with no sort parameter, so collection walks time
**forward** in one-hour windows. The watermark advances only over a window that was fully drained
*and* confirmed pushed, which is what makes collection exhaustive without duplicates across
pagination truncation, container restarts, rejected cursors and outages.

Two files under the connector's data path carry that state:

| File | Contents |
| --- | --- |
| `context.json` | the watermark — end of the last fully drained window |
| `pending.json` | the window in flight — frozen bounds, Slack cursor, ids already forwarded |

## Development

```bash
uv sync
uv run pytest                                    # 86 tests, coverage gate at 80 %
uv run black . && uv run isort .
uv run mypy --install-types --non-interactive --ignore-missing-imports .
uv run sekoia-automation generate-files-from-code
```

`generate-files-from-code` rewrites `main.py` **without** the `register_account_validator` call —
check it survived. `tests/test_main.py` guards this.

## Licence

MIT — see [LICENSE](LICENSE).
