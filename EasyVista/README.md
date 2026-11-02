# EasyVista Service Manager

This action-only integration manages incidents and requests, workflow actions and tasks, documents and questionnaires.

## Prerequisites

Use a dedicated EasyVista user whose profile enables **REST API** access. Allow the HTTP method for each route used by
your playbook. Update and Close also require `GET /requests/{rfc_number}` to check whether the ticket is already closed.
The account validator requires `GET /requests`.

Set `base_url` to the HTTPS protocol and host of the server, without a path. HTTP URLs are rejected to protect credentials.
Set `tenant_id` to the non-empty EasyVista **account** number
used in `/api/v1/{account}`. Keep it as a string to preserve leading zeros.

Bearer authentication is the default. An administrator creates an access token under
**Administration > Access Management > Access Tokens**; configure it as `token`. To use Basic authentication, set
`use_token` to `false` and provide `username` and `password`. Keep TLS verification enabled unless the deployment
requires otherwise.

## Configuration

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `base_url` | string | Yes | — | HTTPS protocol and host of the EasyVista server, without a path, query or credentials. A trailing `/` is removed. HTTP is rejected. |
| `tenant_id` | string | Yes | — | Non-empty EasyVista account number used in the API URL; preserve any leading zeros. Whitespace-only values are rejected. |
| `use_token` | boolean | No | `true` | Use Bearer authentication; set to `false` for Basic authentication. |
| `username` | string | When `use_token = false` | — | REST API user login. |
| `password` | string (secret) | When `use_token = false` | — | REST API user password. |
| `token` | string (secret) | When `use_token = true` | — | EasyVista access token. |
| `verify_ssl` | boolean | No | `true` | Verify the server TLS certificate. |

The selected authentication mode requires non-empty credentials. The account validator checks these requirements
and tests access with `GET /requests?max_rows=1&fields=rfc_number`.

## Troubleshooting

| Error | Check |
| --- | --- |
| `401` | Check the selected authentication mode, its credentials and `tenant_id`. |
| `403` | Enable REST API access on the user's profile and allow the requested route and HTTP method. |
| `404` | Check `base_url`, `tenant_id` and the requested ticket or document identifier. |
| TLS or connection error | Check server reachability and the certificate trust chain when `verify_ssl = true`. |
| `590` | Read the action's EasyVista error message; check ticket state and tenant-specific catalog, action type and group identifiers. For document operations, see the known upload defect below. |

## Behaviour and limitations

- Each API call consumes one EasyVista user license. Update and Close perform an additional read before writing.
- List actions return a single page. `max_rows` controls the page size; automatic pagination is unavailable in 1.0.0.
- POST operations are never retried. A timeout can occur after the server has created an object.
- Error `590` carries EasyVista business errors. The integration reports the response body and does not retry it.
- On some EasyVista deployments, documents uploaded through REST are created but cannot be opened through either
  REST or the UI. This is a vendor defect. Documents attached through the UI can be downloaded and deleted normally.
  When deletion returns `590`, the integration checks the document list and reports success only if the ID is absent
  from a complete list. If another page is advertised, verification fails without fetching additional pages.
- Downloads return base64 and hold the entire file in memory. Large files increase playbook result sizes.
- Questionnaire actions require the numeric action type ID from EasyVista administration, rather than its GUID.
  Empty questionnaire results are successful. These actions require EV SM 2023.4+; document download/deletion
  require 2023.1+ and appending descriptions requires 2025.3+.
- Action types and support groups depend on the tenant and catalog. Related-action creation with `action_type_guid`
  has not been validated on the integration tenant.

## Development

Run `uv sync --locked` and `uv run pytest` from this directory. Unit tests mock all vendor calls; no tenant credentials
are required. Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy easyvista main.py` for linting.

Before release, validate Bearer authentication with a tenant administrator. Live tenant testing and the REST-upload
vendor defect follow-up are external validation steps; the unit tests do not establish live API compatibility.
Never commit credentials or real tenant identifiers.

The module icon comes from the [official EasyVista website](https://www.easyvista.com/wp-content/uploads/EV-Bubble-Pink@4x-1.png).
