## Configuration

This guide supplements the generated action and configuration reference with EasyVista-specific setup and operational guidance.
EasyVista recommends access-token authentication; Basic authentication is also supported.
See the official [REST API authentication documentation](https://docs.easyvista.com/docs/webservice-rest).

### In EasyVista: Configure a dedicated REST API profile

Follow EasyVista's [user profile procedure](https://docs.easyvista.com/docs/profile) to restrict access to the
routes and HTTP methods required by your playbooks.

1. Sign in with an account authorized to manage user profiles.
2. Open `Administration` > `Access Management` > `User Profiles`.
3. Create a dedicated profile, or duplicate an appropriate existing profile, and open its form.
4. Enable the `REST API` option.
5. Click the tools or gear icon next to `REST API` to open the API permissions screen.
6. Select the routes used by your playbooks and enable the corresponding HTTP method columns:
   `GET` for reads, `POST` for creation, `PUT` for updates and state changes, and `DELETE` for document deletion.
7. Save the permissions and the profile.

Grant only the routes and methods needed for your playbooks. In addition to each action's write permissions:

- Account validation requires `GET /requests`.
- Update and Close require `GET /requests/{rfc_number}` for their closed-ticket pre-check.
- Delete Document may need `GET /requests/{rfc_number}/documents` to verify a deletion after a `590` response.

The API root is `/api/v1/{account}`. Placeholder names in the permissions screen may differ from those in the action reference.

### In EasyVista: Assign the profile to a dedicated user

Use the [employee access management procedure](https://docs.easyvista.com/docs/employee) to configure the user
whose permissions the integration will use.

1. Open `Administration` > `Access Management` > `Employees`.
2. Select the dedicated integration user. If you need a new user who is not managed by LDAP or SSO, use `+ New`.
3. Run the `Update Profile` wizard and assign the REST API profile created above.
4. Run `Update Domains` and select the domains containing the tickets the integration should access.
5. Select the appropriate default domain and save the changes.
6. If you created a local user for Basic authentication, verify its login and use the `Change Password` wizard to
   set its password. Keep these credentials for the Sekoia.io account configuration.

### In EasyVista: Generate an access token

Access tokens are available in EV Service Manager 2023.1 and later. The user generating the token must have access
to the token-management menu in their profile. Follow EasyVista's
[access-token procedure](https://docs.easyvista.com/docs/access-tokens):

1. Open `Administration` > `Access Management` > `Access Tokens`.
2. Click `+ New`.
3. Enter a descriptive name, such as `Sekoia.io playbooks`, and select the dedicated integration user.
4. Click `Generate` and securely store the generated value, which is copied to the clipboard.
5. Paste this value into Sekoia.io's `token` field when configuring the account.

> **Note:** The token value is only available when it is generated. Generate a replacement if it is lost.
> If an expiry date is configured, replace the token in Sekoia.io before it expires. A revoked token must also be replaced.

### Identify the server URL and EasyVista account

The vendor's [REST API URL format](https://docs.easyvista.com/docs/webservice-rest) is:

```text
https://{server}/api/v1/{account}/{resource}
```

Obtain the server and account number from your EasyVista administrator:

- `base_url`: the HTTPS protocol and server host only, without `/api/v1` or any other path.
- `tenant_id`: the `{account}` segment, kept as a string to preserve leading zeros. This is the EasyVista account
  number, not the user's login or a Microsoft Entra tenant ID.

For example, use `https://easyvista.example` as a fictitious host and replace `{account}` with your own account number.
The integration constructs the API path; do not append it to `base_url`.

Enter the generated token in Sekoia.io without the `Bearer` prefix. The integration builds the authentication header.
For Basic authentication, use the dedicated user's credentials with the same REST profile and route permissions.
HTTPS remains mandatory even when certificate verification is disabled.

### EasyVista-specific behaviour and limitations

- **Business errors (`590`):** EasyVista can use this non-standard status for invalid identifiers or ticket state.
  Read the response's error message rather than interpreting the status as a generic server failure. The module
  does not retry `590` responses. Suspending an already suspended ticket or restarting one that is not suspended
  fails the action.
- **Closed tickets:** Update and Close read the ticket first and refuse it when `END_DATE_UT` is populated.
  This avoids an apparent API success on an already closed ticket and requires an additional read permission.
- **Appending descriptions:** Requires EV Service Manager 2025.3 or later. Appending is not idempotent, so the
  module never retries a PUT containing the `append` query parameter, whatever its value. EasyVista appends whenever
  this parameter is present, even with `append=false`. The Update action sends it only when `append` is true;
  false or unset replaces the description by omitting the parameter. Check the ticket after an uncertain timeout
  before trying again.
- **Other writes:** POST requests are also never retried because they can create duplicates.
- **Suspend and restart:** These transitions are never retried automatically. After a gateway timeout, check the
  ticket state before trying again: EasyVista may already have applied the transition.
- **Partial updates:** Empty optional text fields are omitted so that untouched playbook fields do not clear existing
  ticket values. To clear a field intentionally, send its EasyVista field name with an empty string in `custom_fields`.
  Non-empty explicit arguments take precedence over matching custom fields.
- **Pagination:** EasyVista paginates GET results from version 2024.3. This module returns only one page and does
  not follow next-page links automatically. A ticket absent from the first page is not necessarily absent from EasyVista.
- **REST-uploaded documents:** On some installations, an API upload succeeds and the attachment is listed, but
  downloading it returns `590` and opening it in the EasyVista UI returns `500`. This is an observed server-side
  issue. If affected, attach files through the EasyVista UI and contact EasyVista support.
- **Document deletion:** A `590` response can occur even when the attachment was removed. The module checks the
  document list and confirms deletion only if the ID is absent from a complete list. If verification fails or another
  page is advertised, the action fails with the original API error instead of reporting an unverified success.
- **Document size:** Downloads are returned as base64 with the entire file held in memory; large documents
  increase playbook result sizes. Document download and deletion require EV Service Manager 2023.1 or later.
- **Questionnaires:** Require EV Service Manager 2023.4 or later and a numeric action type ID from EasyVista
  administration, rather than an action type GUID. Empty questionnaire results are successful.
- **Catalogs, groups and action types:** Their identifiers and permitted combinations depend on your EasyVista
  account. Use values allowed for the ticket's catalog; a rejected action type can produce a misleading catalog error.
- **Licensing:** EasyVista states that each API call consumes a user license. Pre-checks and deletion verification
  make additional calls. See [Licensing and security](https://docs.easyvista.com/docs/webservice-rest#licensing-and-security).

### Verify access and troubleshoot

The account validator performs a read-only request to:

```text
GET /api/v1/{tenant_id}/requests?max_rows=1&fields=rfc_number
```

A successful validation confirms access to the ticket-list route. It does not prove that the user can create,
update, close or delete resources; enable and check the corresponding route and method permissions separately.
Test write actions on a ticket intended for testing.

| Error | What to check |
| --- | --- |
| `401` | The selected authentication mode, token or credentials, and EasyVista account number. |
| `403` | The profile's `REST API` option and permissions for the requested route and method. |
| `404` | The server URL, account number, and requested ticket or document identifier. |
| TLS or connection error | Server reachability and the certificate trust chain. |
| `590` | The API error message, ticket state, and account-specific catalog, group and action-type identifiers. |

### Illustrative playbook flow — not executable

**The following is a conceptual example, not an executable or importable playbook. Do not paste it into the Code tab.**
It contains no node UUIDs, account bindings or runnable JSON structure.

```text
When a Sekoia.io alert needs an EasyVista ticket:
  Create Request / Incident using a catalog allowed for the integration user.
  Save the returned rfc_number with the investigation context.

While the investigation progresses:
  Reuse that rfc_number to update or append investigation details.
  Keep the ticket open until the investigation is resolved.

When the investigation is resolved:
  Close Request / Incident with the resolution comment.
```

To build an executable template, follow the official
[Sekoia.io playbook JSON format and schema](https://docs.sekoia.com/xdr/features/automate/playbooks_format_json_schema/),
use the published module and action UUIDs, and bind the configured EasyVista account in your community.
