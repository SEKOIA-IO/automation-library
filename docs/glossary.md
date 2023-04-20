# Glossary


## Action

An action helps to execute specific tasks (see [definition](https://docs.sekoia.io/xdr/features/automate/actions/)). A [playbooks](#Playbook) is compound of one or more actions.


## Connector

A connector is a specialized [trigger](#Trigger) that fetch events and forward them to SEKOIA.IO. A connector never launches [playbook runs](#Run).


## Module

A module groups a set of [triggers](#Trigger) and [actions](#Actions) sharing a same interest. Most of the time, a module is associated to a product vendor.


## Playbook

A playbook is a recipe aiming to automate recurrent task. It's compound of steps defining a workflow of [actions](#Action).
A playbook always starts with a [trigger](#Trigger).


## Run

A playbook run represents an execution of the [playbook](#Playbook). A run is started by a [trigger](#Trigger), after the detection of a new event.


## Trigger

A trigger is the first step of a [playbook](#Playbook]. The trigger monitors new events and start a new run of the playbook (see [definition](https://docs.sekoia.io/xdr/features/automate/triggers/))

