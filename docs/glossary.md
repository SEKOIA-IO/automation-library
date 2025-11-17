# Glossary

## Action

**Definition**: A component that executes a specific task within a playbook.

**Characteristics**:
- Performs discrete operations (e.g., create user, send email, query API)
- Can accept input parameters defined by a JSON schema
- May return output data for use by subsequent actions
- Multiple actions can be chained together in a playbook

**Reference**: See [Action documentation](action.md) for implementation details and [official definition](https://docs.sekoia.io/xdr/features/automate/actions/).

## Connector

**Definition**: A specialized trigger that collects events from external sources and forwards them to Sekoia.io.

**Characteristics**:
- Fetches events from external systems (APIs, logs, webhooks)
- Continuously forwards collected events to Sekoia.io intake
- Does NOT launch playbook runs (unlike standard triggers)
- Runs in an infinite loop with configurable polling intervals

**Reference**: See [Connector documentation](connector.md) for implementation details.

## Module

**Definition**: A logical grouping of related triggers, actions, and connectors.

**Characteristics**:
- Contains triggers, actions, and/or connectors sharing a common purpose
- Typically associated with a specific product vendor or service
- Has its own manifest file, logo, and configuration schema
- Self-contained with its own Python dependencies

**Reference**: See [Module documentation](module.md) for structure and implementation.

## Playbook

**Definition**: An automated workflow composed of sequential or parallel steps.

**Characteristics**:
- Designed to automate recurring tasks
- Consists of one or more actions arranged in a workflow
- Always begins with a trigger that initiates execution
- Each execution creates a run instance

**Reference**: See [official definition](https://docs.sekoia.io/xdr/features/automate/playbooks/).

## Run

**Definition**: A single execution instance of a playbook.

**Characteristics**:
- Created when a trigger detects a new event
- Executes the playbook's workflow from start to finish
- Has its own execution context and data
- Can succeed, fail, or be cancelled

## Trigger

**Definition**: The initiating component of a playbook that monitors for events.

**Characteristics**:
- Monitors external systems or events
- Starts a new playbook run when an event is detected
- Provides initial data/context to the playbook run
- Can be scheduled (polling) or event-driven (webhook)

**Reference**: See [Trigger documentation](trigger.md) for implementation details and [official definition](https://docs.sekoia.io/xdr/features/automate/triggers/).
