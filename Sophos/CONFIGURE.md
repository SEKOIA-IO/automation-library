### Configure

#### Create an API credential

1. Log in to the Sophos console of the tenant (Sophos Central, or `https://fusion.sophos.com` for a tenant upgraded to Sophos Fusion).
2. Go to `Global Settings` > `API Credentials Management`.
3. Click `Add Credential`.
4. Type a name and select the role required by the connectors you plan to use (see below), then click `Add`.
5. In the `API Credential Summary`, copy the `Client ID` and the `Client Secret`. The secret is shown only once.
6. In Sekoia.io, set them in the Sophos module configuration (`client_id`, `client_secret`). Keep the default `api_host` (`https://api.central.sophos.com`) and `oauth2_authorization_url` (`https://id.sophos.com/api/v2/oauth2/token`).

#### Roles per connector

| Connector | Sophos API | Minimum role |
|---|---|---|
| Get Sophos events | SIEM API `GET /siem/v1/events` | `Service Principal ReadOnly` |
| [BETA] Get Sophos Fusion detections | Detections GraphQL API `POST https://api.taegis.sophos.com/graphql` | `Service Principal ReadOnly` |
| [DEPRECATED] Query IoC from data lake | XDR Data Lake Query API `POST /xdr-query/v1/queries/runs` | `Service Principal Forensics` |
| Device and user assets | `/endpoint/v1`, `/common/v1` | `Service Principal ReadOnly` |
| Isolate, deisolate, scan | `/endpoint/v1` | `Service Principal Management` (refused with ReadOnly and Forensics) |

- `Service Principal ReadOnly` gives read access to all public APIs except forensics: with this role, the legacy IoC connector gets `403 UNAUTHORIZED_ACCESS`.
- `Service Principal Forensics` does not include the read-only access: it reads the endpoints but not the directory users (`403`).
- A credential has a single role and the module a single credential: to use connectors needing different roles, create one module configuration per credential, or use a `Service Principal Super Admin` credential.
- No role is specific to Sophos Fusion.
- The credential must be created on the tenant itself: partner and organization credentials are not supported.

#### Choose the connector: Sophos Fusion or legacy

Sophos has started to upgrade the tenants of Sophos XDR and MDR to **Sophos Fusion**, in a staged rollout and without notice on the API side. Customers onboarded recently start directly on Sophos Fusion.

- **[DEPRECATED] Query IoC from data lake**: the legacy IoC connector, for the tenants **not upgraded yet** only. On an upgraded tenant, the XDR Data Lake Query API still answers but returns no new data: the connector runs without collecting anything, and logs an error when it detects the upgrade. It will be removed once every tenant is upgraded.
- **[BETA] Get Sophos Fusion detections**: its replacement, for the tenants **upgraded to Sophos Fusion** (the console shows `Security Operations` instead of `Threat Analysis Center`). In beta while its parsing is validated on every detection type: report any detection that is not parsed correctly.
- To switch, create a new intake with the Sophos Fusion connector as soon as the console shows the upgrade, then delete the legacy one.
- **Get Sophos events** (SIEM API) is not affected: it keeps working before and after the upgrade.

#### Useful pages of the Sophos console

- `Global Settings` > `API Credentials Management`: API credentials and their roles.
- `Security Operations` > `Detections` (Sophos Fusion): the detections collected by the Fusion connector, with their severity (`Critical`, `High`, `Medium`, `Low`, `Info`) and threat score (0–10).
- `Threat Analysis Center (Classic)` (Sophos Fusion): history of the legacy Threat Analysis Center, read only.
- `Licenses`: XDR / MDR licences. An expired licence stops the detections and can make the XDR APIs answer `403`.

#### Sophos Fusion migration notes

- 2026-07-28: Sophos Fusion launched.
- 2026-09-18: Sophos publishes the XDR GraphQL APIs (Detections, Cases, Events) and announces that the legacy XDR APIs only return data already in retention on upgraded tenants ([What's new](https://developer.sophos.com/whatsnew/sep-18-2026-xdr-graphql-apis/), [Migrating to Sophos Fusion APIs](https://developer.sophos.com/migrate-to-fusion/)).
- 2026-10-12: Search GraphQL API released (data lake queries in Sophos Query Language). It does not support detections, so the Fusion connector uses the Detections API.
- The GraphQL APIs use the same OAuth2 token as the Sophos Central APIs, with the `X-Tenant-ID` header. The GraphQL host is `https://api.taegis.sophos.com` for all data regions, and `whoami` does not return it.
- An upgraded tenant can be recognized with the GraphQL query `tenant(id: <tenant id>) { centralTenant { xdrOwnership hydrateTo } }`: `securityOperations` / `taegis` on an upgraded tenant. Not yet checked on a tenant that is not upgraded.

References: [Detections GraphQL API](https://developer.sophos.com/detections-graphql/), [Detections search](https://developer.sophos.com/detections-graphql-search/), [SIEM API](https://developer.sophos.com/siem/), [Rate limits](https://developer.sophos.com/concepts/rate-limits/).
