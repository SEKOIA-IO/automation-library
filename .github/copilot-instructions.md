# GitHub Copilot Instructions for Automation Library

## Repository Overview

The organization of this repository is described in `docs/README.md`. Please refer to that document for a comprehensive understanding of the repository structure.

## Pull Request Reviews

### Module Identifier Changes

When reviewing pull requests, pay special attention to changes in module identifiers:

- **Always comment** when a module's identifier (ID/UUID) is modified in any configuration file, manifest, or module definition
- Highlight that changing a module identifier is a breaking change that may affect:
  - Existing deployments and installations
  - Module dependencies and references
  - Historical data and configurations
  - Integration with other systems

### Review Checklist

When a module identifier change is detected:
1. Ask if this change is intentional
2. Request confirmation that the impact has been assessed
3. Suggest adding a migration guide or changelog entry
4. Verify that related documentation has been updated
