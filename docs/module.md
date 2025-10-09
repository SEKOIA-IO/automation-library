# Module

## Overview

A module is a logical grouping of related triggers, actions, and connectors. Modules typically correspond to a specific product vendor or service (e.g., Azure Active Directory, Okta, AWS).

## Module Structure

### Required Files

Every module MUST contain:

1. **`manifest.json`** - Module metadata and configuration schema
2. **`logo.png`** - Visual identifier for the module (typically vendor logo)
3. **`CHANGELOG.md`** - Version history and change documentation

### Optional Files

A module MAY contain:

4. **`pyproject.toml`** - Python dependencies specification
5. **`main.py`** - Module entrypoint that registers actions, triggers, and connectors
6. **`<module_name>_module/`** - Directory containing Python implementation code
7. **Component manifest files**:
   - `action_<name>.json` - Action metadata
   - `trigger_<name>.json` - Trigger metadata  
   - `connector_<name>.json` - Connector metadata

## Manifest Specification

The `manifest.json` file defines module metadata using the following schema:

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `uuid` | string (UUID) | Unique identifier for the module | `"d82f8e7c-..."` |
| `name` | string | Human-readable module name | `"Azure Active Directory"` |
| `slug` | string | URL-safe identifier (regex: `[a-z-]+`) | `"azure-ad"` |
| `description` | string | Brief module description | `"Manage Azure AD users and groups"` |
| `version` | string | Semantic version number | `"1.2.3"` |
| `configuration` | object | JSON Schema for module configuration | See below |

### Configuration Schema

The `configuration` field is a JSON Schema object that defines the module-level configuration parameters (e.g., API keys, base URLs, account credentials).

### Versioning

**IMPORTANT**: The `version` field MUST follow [Semantic Versioning](https://semver.org/):
- **MAJOR** version for incompatible API changes
- **MINOR** version for backward-compatible functionality additions
- **PATCH** version for backward-compatible bug fixes

The version MUST be incremented with every change to the module.

## Python Implementation

### Module Class

A module MUST be implemented as a Python class that:
- Inherits from [`Module`](https://github.com/SEKOIA-IO/sekoia-automation-sdk/blob/main/sekoia_automation/module.py) from the `sekoia-automation-sdk`
- Defines its configuration as a [Pydantic model](https://docs.pydantic.dev/)

**Example**:
```python
from sekoia_automation import Module
from pydantic import BaseModel

class AzureADConfiguration(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str

class AzureADModule(Module):
    configuration: AzureADConfiguration
```

### Entrypoint (`main.py`)

The `main.py` file:
- Instantiates the module class
- Registers actions, triggers, and connectors with their corresponding manifest files
- Associates each component with its unique command name (`docker_parameter`)

**Example**:
```python
from azure_ad_module import AzureADModule
from azure_ad_module.actions import EnableUserAction
from azure_ad_module.triggers import UserEventTrigger

if __name__ == "__main__":
    module = AzureADModule()
    module.register(EnableUserAction, "enable_user")
    module.register(UserEventTrigger, "user_events")
    module.run()
```

## Component Organization

Actions, connectors, and triggers each consist of:
1. **Python implementation** - Located in `<module_name>_module/` directory
2. **JSON manifest** - Located in module root directory

See component-specific documentation:
- [Action Documentation](action.md)
- [Trigger Documentation](trigger.md)
- [Connector Documentation](connector.md)

## Dependencies

The `pyproject.toml` file specifies Python dependencies using Poetry format. This file defines all packages required by the module's actions, triggers, and connectors.

## Example Module

Reference implementation: [Azure Active Directory module](https://github.com/SEKOIA-IO/automation-library/tree/main/Azure)
