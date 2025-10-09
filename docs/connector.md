# Connector

A Connector collects raw event logs and forward them to Sekoia.io.

- A manifest file in the root directory of the module. The manifest of an connector is prefixed with the string `connector_`.
  This document contains:
  	- The unique identifier of the connector (field `uuid`)
	- The name of the connector (field `name`)
	- A short description about that the connector (field `description`)
	- The unique command name of the connector (field `docker_parameter`)
	- A description of the configuration of the connector (field `arguments`). This description is a [JSON schema model](https://json-schema.org/)

- A python code

## Python code

A Connector is a class based on [`Connector`](https://github.com/SEKOIA-IO/sekoia-automation-sdk/blob/main/sekoia_automation/connector.py) from [sekoia-automation-sdk](https://github.com/SEKOIA-IO/sekoia-automation-sdk/).

It must implement the method `run` and call the method `publish_events_to_intake` to forward events.

The `run` works as an infinite loop like this pseudo code:

```python
while True:
    events = self.fetch_events()  # fetch new events from the source
    if events:
        self.publish_events_to_intake(events)  # forward events to Sekoia.io
    sleep(self.configuration.frequency)  # wait for the next polling
```

(See [OKTA system log connector](../Okta/okta_modules/system_log_trigger.py))


## Entrypoint

To expose a connector of the module, the connector must be declared in `main.py` at the root of the module.

Import the class in `main.py` and register the class, against the module, with the unique command name of the connector as second argument.

(See [Okta main.py](../Okta/main.py))
