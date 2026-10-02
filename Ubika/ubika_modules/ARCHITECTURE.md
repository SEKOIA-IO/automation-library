# Architecture

## Connectors

### `connector_ubika_cloud_protector_next_gen_traffic_logs`

Connector for Ubika Cloud Protector NextGen Traffic Logs.

---

### Specifications & Implementation Notes

#### 1. Polling endpoint

```
GET https://api.ubika.io/rest/logs.ubika.io/v1/ns/{namespace}/traffic-logs
```

Query parameters:

| Parameter               | Description                        |
|-------------------------|------------------------------------|
| `filters.fromDate`      | Last seen timestamp (ms)           |
| `pagination.pageSize`   | Number of items per page           |
| `pagination.realtime`   | Set to `True`                      |

Use `nextPageToken` to paginate until the items list is empty.

---

#### 2. Checkpoint strategy (cursor-based)

- On startup, read `most_recent_timestamp_seen` from `context.json`.
- If none, backfill `start_time` hours by calling from `now - start_time * 3600 * 1000`.
- After fetching all pages, persist the maximum timestamp seen.
- Next poll uses that timestamp as the new `filters.fromDate`.

---

#### 3. Infinite loop (`run()`)

- Calls `process_batch(start_ts)` to page, serialize and push events.
- Sleeps `frequency` seconds between iterations.
- Stops when `_stop_event` is set, then saves the final checkpoint.

---

#### 4. Publishing

Events are serialized with `orjson` and forwarded via:

```python
self.push_events_to_intakes(events=...)
```

---

#### 5. Error handling

- `_handle_response_error()` raises `FetchEventsException` on non-2xx status codes.
- `AuthorizationError` and `AuthorizationTimeoutError` bubble up.

---

#### 6. Configuration (Pydantic model)

| Field           | Description                          |
|-----------------|--------------------------------------|
| `namespace`     | Ubika namespace                      |
| `refresh_token` | API refresh token                    |
| `frequency`     | Polling interval in seconds          |
| `chunk_size`    | Maximum items per page               |
| `start_time`    | Hours to backfill on first run       |

---

#### 7. HTTP client

Provided by `UbikaCloudProtectorNextGenApiClient` via a `@cached_property`. Manages token refresh and rate limits under the hood.

---

### Design goals

- Single `fromDate` cursor for checkpoint management
- `nextPageToken`-based pagination
- Continuous collection loop

## Authors

- [Clement Burtscher](https://github.com/clement-burtscher-sekoia)
- [Sébastien Quioc](https://github.com/squioc)
