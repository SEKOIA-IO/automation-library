# Connector

## Overview

A connector is a specialized component that collects raw event logs from external sources and forwards them to Sekoia.io's intake system. Unlike triggers, connectors do NOT launch playbook runs—they only collect and forward event data for ingestion.

## Connector vs Trigger

**Connector**: Collects events and forwards to Sekoia.io intake using `publish_events_to_intake()`  
**Trigger**: Monitors events and launches playbook runs using `send_event()`

Use connectors for event ingestion and triggers for workflow automation.

## Connector Components

Each connector consists of TWO required components:

### 1. Manifest File (JSON)

**Location**: Module root directory  
**Naming convention**: `connector_<name>.json`

#### Manifest Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | string (UUID) | Yes | Unique identifier for the connector (MUST NOT change) |
| `name` | string | Yes | Human-readable connector name |
| `description` | string | Yes | Brief description of what the connector collects |
| `docker_parameter` | string | Yes | Unique command name for connector registration |
| `arguments` | object (JSON Schema) | Yes | Configuration schema for the connector |

#### Important Notes

- The `uuid` is the connector's permanent identifier. **Changing it is a breaking change.**
- The `arguments` field defines connector configuration (e.g., API credentials, polling frequency, filters)
- Uses [JSON Schema](https://json-schema.org/) format
- Connectors do NOT have a `results` field (events are forwarded, not returned)

### 2. Python Implementation

**Location**: `<module_name>_module/` directory

#### Class Structure

A connector class MUST:

1. **Inherit from** [`Connector`](https://github.com/SEKOIA-IO/sekoia-automation-sdk/blob/main/sekoia_automation/connector.py) (from `sekoia-automation-sdk`)
2. **Implement the `run()` method**:
   - Contains an infinite loop for continuous event collection
   - Calls `self.publish_events_to_intake()` to forward events
   - Handles polling intervals and error recovery

#### Event Forwarding

When events are collected, call `self.publish_events_to_intake()` to forward them to Sekoia.io:

```python
self.publish_events_to_intake(events)
```

**Example**:
```python
from sekoia_automation import Connector, DefaultConnectorConfiguration
import time

class SystemLogConfiguration(DefaultConnectorConfiguration):
    api_key: str
    polling_interval: int = 60

class SystemLogConnector(Connector):
    configuration: SystemLogConfiguration
    
    def run(self):
        """
        Continuously collect and forward events.
        This method runs in an infinite loop.
        """
        while True:
            try:
                # 1. Fetch new events from source
                events = self.fetch_events()
                
                # 2. Forward events to Sekoia.io if any exist
                if events:
                    self.publish_events_to_intake(events)
                
                # 3. Wait before next poll
                time.sleep(self.configuration.frequency)
                
            except Exception as e:
                self.log_exception(e)
                time.sleep(60)  # Error backoff
    
    def fetch_events(self):
        """Fetch events from external source."""
        # Implementation specific to data source
        pass
```

**Reference implementation**: See [Okta system log connector](../Okta/okta_modules/system_log_trigger.py)

## Registration

Connectors MUST be registered in the module's `main.py` entrypoint.

### Registration Steps

1. Import the connector class
2. Register the class with the module using `module.register()`
3. Pass the `docker_parameter` value as the second argument

**Example**:
```python
from module_name_module import ModuleClass
from module_name_module.connectors import SystemLogConnector

if __name__ == "__main__":
    module = ModuleClass()
    module.register(SystemLogConnector, "system_log")  # "system_log" matches docker_parameter
    module.run()
```

**Reference implementation**: See [Okta main.py](../Okta/main.py)

## Execution Pattern

Connectors follow this standard pattern:

```python
def run(self):
    """
    Infinite loop pattern for event collection.
    """
    while True:
        try:
            # 1. Fetch new events from source
            events = self.fetch_events()
            
            # 2. Forward events to Sekoia.io intake
            if events:
                self.publish_events_to_intake(events)
            
            # 3. Wait before next poll
            time.sleep(self.configuration.frequency)
            
        except Exception as e:
            # 4. Handle errors gracefully
            self.log_exception(e)
            time.sleep(self.configuration.error_backoff)
```

## Key Differences from Triggers

| Aspect | Connector | Trigger |
|--------|-----------|---------|
| Purpose | Event ingestion | Playbook initiation |
| Method | `publish_events_to_intake()` | `send_event()` |
| Output | Forwards to Sekoia.io intake | Launches playbook runs |
| Manifest | No `results` field | Has `results` field |
| Use case | Log collection, data forwarding | Workflow automation |

## Schema Synchronization

**CRITICAL**: The configuration model in Python MUST match the JSON Schema in the manifest's `arguments` field:
- Property names, types, and constraints must align
- Mismatches will cause runtime validation errors
