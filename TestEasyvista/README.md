# Test EasyVista Service Manager

Test module holding only the `EasyVista Devices` asset connector, without the playbook actions of the
`EasyVista Service Manager` module. It is used to test custom asset connectors.

## Prerequisites

Use a dedicated EasyVista user whose profile enables **REST API** access with `GET /assets`. The account validator
calls `GET /requests` and falls back to `GET /assets` when the profile is denied access to requests (`403`).

Set `base_url` to the HTTPS protocol and host of the server, without a path. Set `tenant_id` to the EasyVista
**account** number used in `/api/v1/{account}`, as a string to keep leading zeros. Bearer authentication (`token`)
is the default; set `use_token` to `false` to use `username` and `password` instead.

## Asset connector

`EasyVista Devices` lists every asset of `GET /assets` at each cycle (optionally restricted by the `search`
expression), keeps those with a network identifier usable as hostname, skips removed and recycled assets, and pushes
only the devices whose OCSF output changed since the previous cycle.
