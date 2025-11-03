# Organization

## Repository Structure

This repository is organized into modules, where each module is a self-contained directory.

## Module Organization

Each module groups related components:
- **Triggers**: Components that monitor events and initiate playbook execution
- **Actions**: Components that execute specific tasks within playbooks
- **Connectors**: Components that collect and forward events to Sekoia.io

## Directory Layout

```
automation-library/
├── ModuleName/
│   ├── manifest.json           # Module metadata and configuration
│   ├── logo.png                # Module visual identifier
│   ├── CHANGELOG.md            # Version history
│   ├── pyproject.toml          # Python dependencies
│   ├── main.py                 # Module entrypoint
│   ├── action_*.json           # Action manifests
│   ├── trigger_*.json          # Trigger manifests
│   ├── connector_*.json        # Connector manifests
│   └── module_name/     # Python implementation code
│       ├── actions/
│       ├── triggers/
│       └── connectors/
└── AnotherModule/
    └── ...
```

## Key Principles

- Each module is independent and self-contained
- Modules typically correspond to a product vendor or service
- All module components share a common configuration schema defined in the module manifest

For detailed information about module structure, see [Module](module.md).
