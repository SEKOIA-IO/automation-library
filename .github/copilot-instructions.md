# GitHub Copilot Instructions for Automation Library

## Repository Overview

The organization of this repository is described in `docs/README.md`. Please refer to that document for a comprehensive understanding of the repository structure.

## Pull Request Reviews

### Component Identifier Changes

When reviewing pull requests, pay special attention to changes in component identifiers for modules, actions, connectors, and triggers:

- **Always comment** when a component's identifier (ID/UUID) is modified in any configuration file, manifest, or component definition
- Highlight that changing a component identifier is a breaking change that may affect:
  - Existing deployments and installations
  - Component dependencies and references
  - Historical data and configurations
  - Integration with other systems

### Review Checklist

When a component identifier change is detected:
1. Ask if this change is intentional
2. Request confirmation that the impact has been assessed
3. Suggest adding a migration guide or changelog entry
4. Verify that related documentation has been updated
