### Configure

#### Create an Azure application

1. On the Azure Portal, in the search bar, go to `App registrations`
2. Click `+ New registration`
3. Type a name
4. Select `Accounts in this organizational directory only` option as account type
5. Click `Register`
6. From the `Overview` page, copy `Application (client) ID` and `Directory (tenant) ID`

#### Create a client secret

1. Go to `Manage` > `Certificates & secrets`
2. Click `+ New client secret`
3. Type a description and select the desired expiration period
4. Click `Add`
5. Copy the `Value` of the client secret

#### Add permissions

The following steps configure Microsoft Entra application permissions. For a new deployment restricted to selected
mailboxes, use the Exchange Online RBAC alternative below rather than granting equivalent unscoped permissions.

1. Go to `Manage` > `API permissions`
2. Click `Add a permissions`
3. On the right panel, Select `Microsoft APIs` tab
4. Click `Microsoft Graph`
5. Click `Application permissions`
6. Select application permissions for the operations you will use:

    | Operations | Permission |
    | --- | --- |
    | Collect, get, search, list, download, extract or export messages | `Mail.Read` |
    | Move, delete or update messages, or mark collected reports as read | `Mail.ReadWrite` |
    | Send or forward messages | `Mail.Send` |

    `Mail.ReadWrite` includes read access. Directory-wide user lookup permissions are not required by these actions.
7. Click `Add permissions`.
8. On the `API permissions` page, click `Grant admin consent for TENANT_NAME` and confirm.

See Microsoft's [mail attachment permissions](https://learn.microsoft.com/en-us/graph/api/message-list-attachments?view=graph-rest-1.0)
and [message retrieval API](https://learn.microsoft.com/en-us/graph/api/message-get?view=graph-rest-1.0).
Scope the application's mailbox access according to your organization's Exchange Online access controls.

#### Restrict mailbox access

Choose the mailbox scope according to the workflow:

| Workflow | Mailboxes that must be accessible |
| --- | --- |
| Collect reports and extract the originals attached to them | Reporting mailbox only |
| Find or export copies in recipient mailboxes | Reporting mailbox and authorized recipient mailboxes |
| Move, delete or update recipient copies | Authorized target mailboxes with write access |

Separate application registrations and Sekoia accounts can isolate reporting-mailbox collection from broader
investigation or remediation access. The module uses the same tenant/client credentials in either authorization model.

For new restricted deployments, use [RBAC for Applications in Exchange Online](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac):

1. Register the existing Entra enterprise application's service principal in Exchange Online. Use its enterprise
   application object ID, not the app registration object ID.
2. Define a management scope containing only the intended mailboxes.
3. Assign the necessary scoped role: `Application Mail.Read`, `Application Mail.ReadWrite` or `Application Mail.Send`.
4. Check included and excluded mailboxes with `Test-ServicePrincipalAuthorization` and actual Graph requests.

Entra grants and Exchange RBAC assignments are additive. A scoped RBAC assignment does not restrict an equivalent
tenant-wide Entra grant. When adopting RBAC, review and remove equivalent unscoped grants that would bypass the scope.
The test cmdlet evaluates RBAC only; it does not include separate Entra grants. Allow permission changes to propagate
before relying on live authorization results. Existing Application Access Policy deployments should follow Microsoft's
migration guidance.

These application scopes select mailboxes, not individual messages or folders. A mailbox-limited `Mail.Read` grant
allows reading messages throughout that mailbox. Connector folder filters, subject filters and Message-ID arguments
limit requested data but are not permission boundaries.

`Mail.ReadWrite` includes read access but not sending; grant `Mail.Send` only when sending or forwarding is required.
`Mail.ReadBasic.All` is insufficient for this connector's body and attachment extraction. See the
[Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference).

The application does not require personal Outlook `Full Access` delegation for an analyst. Such delegation is a
separate user-access mechanism for opening a mailbox in Outlook and does not configure the application's Graph scope.
Message Trace collection uses separate permissions and is not configured by this Outlook module.

#### Collect reported emails

Configure Microsoft 365 user reporting to deliver reported emails to an Exchange Online reporting mailbox.
Set the connector's `user` to that mailbox's user ID or UPN and `folder` to a Graph folder ID or a well-known name
such as `inbox`. Localized display names and folder paths are not supported.
The connector uses Microsoft Graph mail APIs; it does not use Defender advanced hunting or remediation APIs.

`offset_hours` defines the initial collection window. Subsequent cycles resume from the persisted checkpoint;
changing this value does not rewind an existing checkpoint. `polling_interval` is expressed in seconds and
`overlap_seconds` controls the overlap used to catch late arrivals. Changing the account, mailbox or folder starts
an independently scoped checkpoint. Enable `mark_as_read` only when the application has `Mail.ReadWrite`.

Use an intake format compatible with this connector's phishing-report events. Each extracted original produces
one event linked to its reporting message. Reports with missing or incomplete evidence produce explicit status
information. Delivery is at least once: a restart after delivery but before checkpoint persistence can replay events.

Connector logs report submissions processed and extraction outcomes per emitted event (`complete`, `partial` or
`failed`). Submissions without an embedded email are called out when present. A submission can still contain multiple
originals and produce multiple events. Processing totals exclude overlap duplicates and are recorded after checkpoint
persistence. Intake acceptance remains in the detailed runtime logs; it does not confirm event indexing or searchability.

Routine messages include the last-run duration and the next batch delay, or indicate immediate pagination/stopping.
One compact message is emitted at the end of every run, including runs with no new submissions. Counts reset after
each message; there is no five-minute idle logging delay. Additional per-step details stay in the runtime logs.
With the default 60-second polling wait, routine reporting remains around 60 entries per hour plus startup/shutdown.
Shorter polling waits or rapid paginated backfills can exceed the platform's connector-log allowance; collecting events
and saving checkpoints do not depend on whether a log is retained. Failed collection attempts and failed intake
deliveries are reported separately from empty successful checks; intake delivery failures retain the checkpoint for retry.

#### Extract email evidence

`Extract embedded emails` returns attached EML/MSG messages and their available header, body, URL and attachment
metadata. Transport headers are available as an ordered `headers` list and a `headers_map` object whose lowercase
keys contain arrays of values. Repeated headers are preserved. MSG transport headers are not synthesized when
absent; check `headers_available`. Authentication fields report source headers, not independently verified verdicts.

Inline images are included in attachment evidence even without a filename. Available Content-ID and disposition
metadata can be used to associate them with the HTML body. Remotely hosted images are not downloaded.
Nested attached emails are recorded as attachments; they are not recursively investigated.

Attachment processing is limited to 4 MiB per downloaded attachment. If original nested attachment bytes are
unavailable, size and SHA-256 are omitted or null with a processing error; regenerated bytes are never presented
as original evidence. Incomplete parsing or lossy charset recovery is reported explicitly.

#### Export a message as EML

Use `Export a message as EML` with the mailbox `user` and Graph `message_id`. An Internet Message-ID is not a Graph
item ID: resolve it with `Search messages` first. Exporting a message downloads the MIME content provided by Graph
without reconstructing it, and does not modify the mailbox.

The action writes a generated `.eml` filename into playbook shared storage and returns `file_path`, `file_name`,
`content_type`, `size` and `sha256`. Pass `file_path` to a downstream action supporting shared-storage files in the
same playbook run. Cross-run file access is not implied. The default limit is 25 MiB; `max_size_mb` allows 1–100 MiB.
Interrupted, empty and oversized exports fail without returning a completed file; incomplete files are removed.

#### Handle action outcomes

Inspect `outcome` and `error_details`. Partial, failed or unknown outcomes also mark the action as failed for
playbook branching, while recovered results remain available. After a modifying request times out, its result may
be unknown: verify the current message state before retrying. A move returns the resulting message ID and a
separate destination verification status; reuse the returned ID for subsequent operations.
