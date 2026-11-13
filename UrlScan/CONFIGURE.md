## Create a team API key

A team key is recommended: it uses the team quotas and features, is not tied to a user, and every team member sees it. Scans submitted with it are visible to all team members.

1. Log in to [urlscan.io](https://urlscan.io) and open the [`User`](https://urlscan.io/user/) tab.
2. Go to `Manage Team` > `<your team>` > `Team API Keys`.
3. Click `➕ New Team API key`, set a comment (e.g. `Sekoia.io playbooks`) and validate.

## Retrieve the key

The API has no endpoint to list or retrieve keys, and no login endpoint. Only the user who created the key can copy it: in `Team API Keys`, reveal the masked key in the `Key Details` column and paste it in the `API key` field of the module configuration.

## Check the key

```bash
curl -s -H "API-Key: $API_KEY" https://urlscan.io/user/username   # must reference your team
curl -s -H "API-Key: $API_KEY" https://urlscan.io/api/v1/quotas    # "scope": "team"
```

`401` means the key is invalid or disabled. Key activity: `Last Activity` column, or `GET https://urlscan.io/api/v1/activity/user` / `activity/team`.
