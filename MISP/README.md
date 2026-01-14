## Triggers

### MISP Events Trigger

Monitors MISP for new published events and triggers playbook execution.

**Configuration:**
- `sleep_time`: Polling interval (default: 60 seconds)
- `attributes_filter`: Attribute freshness filter (default: 0 = disabled)

### MISP IDS Attributes to IOC Collection Trigger (NEW)

Periodically retrieves IDS-flagged attributes from MISP and pushes them to a Sekoia.io IOC Collection.

**Configuration:**
- `ioc_collection_server`: Sekoia API server URL
- `ioc_collection_uuid`: Target IOC Collection UUID
- `sekoia_api_key`: API key with write permissions
- `publish_timestamp`: Time window for attribute retrieval (default: 1 day)
- `sleep_time`: Polling interval (default: 300 seconds)

**Use Case:** Automatically import threat indicators from your MISP instance into Sekoia for detection and alerting.

**Supported IOC Types:** ip-dst, domain, url, sha256, md5, sha1

See [docs/trigger_misp_ids_to_ioc_collection.md](docs/trigger_misp_ids_to_ioc_collection.md) for detailed configuration instructions.
