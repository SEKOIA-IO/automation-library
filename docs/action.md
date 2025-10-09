# Action

## Overview

An action is a component that executes a specific task within a playbook. Actions are the building blocks of automation workflows and can perform operations such as API calls, data transformations, user management, or any other discrete task.

See [official documentation](https://docs.sekoia.io/xdr/features/automate/actions/) for end-user perspective.

## Action Components

Each action consists of TWO required components:

### 1. Manifest File (JSON)

**Location**: Module root directory  
**Naming convention**: `action_<name>.json`

#### Manifest Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | string (UUID) | Yes | Unique identifier for the action (MUST NOT change) |
| `name` | string | Yes | Human-readable action name |
| `description` | string | Yes | Brief description of what the action does |
| `docker_parameter` | string | Yes | Unique command name for action registration |
| `arguments` | object (JSON Schema) | Yes | Input parameter schema for the action |
| `results` | object (JSON Schema) | No | Output schema (empty object if no output) |

**Example manifest**: See [Azure AD Enable User action](../AzureActiveDirectory/action_enable_user.json)

#### Important Notes

- The `uuid` is the action's permanent identifier. **Changing it is a breaking change.**
- The `arguments` and `results` fields use [JSON Schema](https://json-schema.org/) format
- The `docker_parameter` must match the registration name in `main.py`

### 2. Python Implementation

**Location**: `<module_name>_module/` directory

#### Class Structure

An action class MUST:

1. **Inherit from** [`Action`](https://github.com/SEKOIA-IO/sekoia-automation-sdk/blob/main/sekoia_automation/action.py) (from `sekoia-automation-sdk`)
3. **Implement the `run()` method**:
   - Accepts argument model as parameter
   - Returns result model (or None)
   - Contains the action's business logic

#### Pydantic Models

The arguments and results MUST be defined as a Python dictionary or as [Pydantic models](https://docs.pydantic.dev/) that mirror the JSON Schema in the manifest.

**Example** (with Pydantic models):
```python
from sekoia_automation import Action
from pydantic import BaseModel

class EnableUserArguments(BaseModel):
    user_id: str

class EnableUserResults(BaseModel):
    success: bool
    user_email: str

class EnableUserAction(Action):
    name = "Enable User"
    description = "Enable a user account in Azure AD"
    
    def run(self, arguments: EnableUserArguments) -> EnableUserResults:
        # Action implementation
        user = self.enable_user(arguments.user_id)
        return EnableUserResults(
            success=True,
            user_email=user.email
        )
```

**Reference implementation**: See [Azure AD Enable User code](../AzureActiveDirectory/azure_ad/user.py)

## Registration

Actions MUST be registered in the module's `main.py` entrypoint.

### Registration Steps

1. Import the action class
2. Register the class with the module using `module.register()`
3. Pass the `docker_parameter` value as the second argument

**Example**:
```python
from module_name_module import ModuleClass
from module_name_module.actions import EnableUserAction

if __name__ == "__main__":
    module = ModuleClass()
    module.register(EnableUserAction, "enable_user")  # "enable_user" matches docker_parameter
    module.run()
```

**Reference implementation**: See [Azure AD main.py](../AzureActiveDirectory/main.py)

## Schema Synchronization

**CRITICAL**: The arguments and the result in Python MUST match the JSON Schema in the manifest:
- Property names must be identical
- Data types must be compatible
- Required/optional fields must align
- Nested structures must match

Mismatches will cause runtime validation errors.
