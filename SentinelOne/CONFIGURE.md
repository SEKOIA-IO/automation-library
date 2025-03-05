## Explanation of Additional Configuration

### Update Threat Incident [Filter attribut]

For the action `Update Threat Incident`, there are two arguments `status` and `filters`. `filters` argument is an object, so in this section, we will explain the components within this argument.

**Arguments**

| Name      |  Type   |  Description  |
| --------- | ------- | --------------------------- |
| `agent_ids` | `string` | List of Agent IDs to filter by |
| `account_ids` | `array` | List of Account IDs to filter by |
| `group_ids` | `array` | List of network group to filter by |
| `site_ids` | `array` | List of Site IDs to filter by |
| `ids` | `array` | List of threat IDs |
| `analyst_verdicts` | `string` | Verdicts of the analyst |