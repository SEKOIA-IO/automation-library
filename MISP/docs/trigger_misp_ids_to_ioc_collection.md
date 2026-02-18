# MISP IDS Attributes to IOC Collection Trigger

## Overview

This trigger periodically retrieves IDS-flagged attributes from a MISP instance and pushes them to a Sekoia.io IOC Collection. Attributes with the `to_ids` flag enabled in MISP are automatically imported as IOCs in Sekoia, enabling detection and alerting when these indicators are observed in your environment.

## Prerequisites

1. **MISP Instance**: Access to a MISP instance with published events containing IDS-flagged attributes
2. **MISP API Key**: Valid API key with read permissions
3. **Sekoia IOC Collection**: Pre-created IOC Collection in your Sekoia.io community
4. **Sekoia API Key**: API key with write permissions to the IOC Collection

## Configuration

### Step 1: Obtain MISP Credentials

1. Log in to your MISP instance
2. Navigate to **Event Actions** > **Automation**
3. Copy your **Authkey** (this is your MISP API key)
4. Note your MISP instance URL (e.g., `https://misp.example.com`)

### Step 2: Create Sekoia IOC Collection

1. Log in to Sekoia.io
2. Navigate to **Intelligence Center** > **IOC Collections**
3. Click **Create IOC Collection**
4. Provide a name (e.g., "MISP IDS Indicators")
5. Copy the **IOC Collection UUID** (format: `ioc-collection--xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### Step 3: Generate Sekoia API Key

1. In Sekoia.io, navigate to **Settings** > **API Keys**
2. Click **Create API Key**
3. Grant **Write** permissions to **IOC Collections**
4. Copy the generated API key

### Step 4: Configure the Trigger in Sekoia Playbooks

1. Navigate to **Playbooks** > **Create Playbook**
2. Add a trigger and select **MISP IDS Attributes to IOC Collection**
3. Configure the following parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| **MISP URL** | URL of your MISP instance | `https://misp.example.com` |
| **MISP API Key** | Your MISP authentication key | `<your_misp_api_key>` |
| **IOC Collection Server** | Sekoia API server URL | `https://api.sekoia.io` |
| **IOC Collection UUID** | UUID of your IOC Collection | `ioc-collection--12345678-...` |
| **Sekoia API Key** | API key with write permissions | `sio_xxxxxxxxxxxxxx...` |
| **Published x days ago** | Number of days to look back for attributes | `1` (default) |
| **Sleep Time** | Polling interval in seconds | `300` (default: 5 minutes) |

4. Save and activate the playbook

## Supported IOC Types

The following MISP attribute types are supported:

- `ip-dst`: Destination IP address → Sekoia `ipv4-addr.value`
- `domain`: Domain name → Sekoia `domain-name.value`
- `url`: Full URL → Sekoia `url.value`
- `sha256`: SHA-256 hash → Sekoia `file.hashes.SHA-256`
- `md5`: MD5 hash → Sekoia `file.hashes.MD5`
- `sha1`: SHA-1 hash → Sekoia `file.hashes.SHA-1`

**Note**: Only attributes with the `to_ids` flag enabled in MISP will be imported.

## How It Works

1. **Polling**: The trigger polls your MISP instance every `sleep_time` seconds
2. **Filtering**: Retrieves attributes with `to_ids=1` published within the configured time window
3. **Type Filtering**: Only supported IOC types are processed
4. **Deduplication**: Previously processed attributes are skipped using a cache
5. **Batching**: IOCs are grouped and sent to Sekoia in batches of up to 1,000 per request
6. **Storage**: IOCs are added to your IOC Collection in Sekoia

## Troubleshooting

### No IOCs are being imported

- Verify your MISP API key has read permissions
- Check that MISP events are published and contain attributes with `to_ids=1`
- Ensure the `publish_timestamp` window is appropriate (try increasing it)
- Review trigger logs in Sekoia.io for errors

### Authentication errors

- Verify MISP URL is correct and accessible
- Check MISP API key is valid and not expired
- Verify Sekoia API key has write permissions to the IOC Collection
- Ensure IOC Collection UUID is correct

### Rate limiting

- Increase the `sleep_time` parameter to reduce polling frequency
- Check MISP instance rate limits

## Best Practices

- Start with a small `publish_timestamp` value (e.g., 1 day) and increase if needed
- Monitor the trigger logs to ensure IOCs are being processed successfully
- Link the IOC Collection to appropriate detection rules in Sekoia
- Regularly review the IOC Collection to ensure relevant indicators are being imported

## Support

For issues or questions, please contact Sekoia support or refer to:
- [Sekoia.io Documentation](https://docs.sekoia.io)
- [MISP Project Documentation](https://www.misp-project.org/documentation/)