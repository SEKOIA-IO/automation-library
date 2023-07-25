from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from darktrace_modules import DarktraceModule
from darktrace_modules.threat_visualizer_log_trigger import ThreatVisualizerLogConnector


@pytest.fixture
def trigger(symphony_storage):
    module = DarktraceModule()
    trigger = ThreatVisualizerLogConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {"api_url": "https://api_url", "private_key": "private", "public_key": "public"}
    trigger.configuration = {
        "intake_key": "intake_key",
    }
    yield trigger


@pytest.fixture
def message1():
    # flake8: noqa
    return [
        {
            "commentCount": 0,
            "pbid": 25808,
            "time": 1687774142000,
            "creationTime": 1687774148000,
            "model": {
                "then": {
                    "name": "Compromise: :Watched Domain",
                    "pid": 608,
                    "phid": 6768,
                    "uuid": "80010119-6d7f-0000-0305-5e0000000123",
                    "logic": {
                        "data": [
                            {"cid": 13112, "weight": 1},
                            {"cid": 13114, "weight": 1},
                            {"cid": 13115, "weight": 1},
                            {"cid": 13113, "weight": 1},
                        ],
                        "targetScore": 1,
                        "type": "weightedComponentList",
                        "version": 1,
                    },
                    "throttle": 3600,
                    "sharedEndpoints": False,
                    "actions": {
                        "alert": True,
                        "antigena": {},
                        "breach": True,
                        "model": True,
                        "setPriority": False,
                        "setTag": False,
                        "setType": False,
                    },
                    "tags": ["", "AP: C2 Comms"],
                    "interval": 3600,
                    "delay": 0,
                    "sequenced": False,
                    "active": True,
                    "modified": "2022-06-22 15: 56: 27",
                    "activeTimes": {"devices": {}, "tags": {}, "type": "exclusions", "version": 2},
                    "autoUpdatable": True,
                    "autoUpdate": True,
                    "autoSuppress": True,
                    "description": "A device is observed making DNS requests or connections to watched domains or IP addresses. The watch list can be edited from the main GUI menu, Intel sub-menu, under the icon Watched Domains.\n\nAction: Review the domain and IP being connected to.",
                    "behaviour": "decreasing",
                    "defeats": [],
                    "created": {"by": "System"},
                    "edited": {"by": "System"},
                    "version": 31,
                    "priority": 5,
                    "category": "Critical",
                    "compliance": False,
                },
                "now": {
                    "name": "Compromise: :Watched Domain",
                    "pid": 608,
                    "phid": 6768,
                    "uuid": "80010119-6d7f-0000-0305-5e0000000123",
                    "logic": {
                        "data": [
                            {"cid": 13112, "weight": 1},
                            {"cid": 13114, "weight": 1},
                            {"cid": 13115, "weight": 1},
                            {"cid": 13113, "weight": 1},
                        ],
                        "targetScore": 1,
                        "type": "weightedComponentList",
                        "version": 1,
                    },
                    "throttle": 3600,
                    "sharedEndpoints": False,
                    "actions": {
                        "alert": True,
                        "antigena": {},
                        "breach": True,
                        "model": True,
                        "setPriority": False,
                        "setTag": False,
                        "setType": False,
                    },
                    "tags": ["", "AP: C2 Comms"],
                    "interval": 3600,
                    "delay": 0,
                    "sequenced": False,
                    "active": True,
                    "modified": "2022-06-22 15: 56: 27",
                    "activeTimes": {"devices": {}, "tags": {}, "type": "exclusions", "version": 2},
                    "autoUpdatable": True,
                    "autoUpdate": True,
                    "autoSuppress": True,
                    "description": "A device is observed making DNS requests or connections to watched domains or IP addresses. The watch list can be edited from the main GUI menu, Intel sub-menu, under the icon Watched Domains.\n\nAction: Review the domain and IP being connected to.",
                    "behaviour": "decreasing",
                    "defeats": [],
                    "created": {"by": "System"},
                    "edited": {"by": "System"},
                    "message": "Adjusting model logic for proxied connections",
                    "version": 31,
                    "priority": 5,
                    "category": "Critical",
                    "compliance": False,
                },
            },
            "triggeredComponents": [
                {
                    "time": 1687774141000,
                    "cbid": 25885,
                    "cid": 13112,
                    "chid": 20980,
                    "size": 1,
                    "threshold": 0,
                    "interval": 3600,
                    "logic": {
                        "data": {
                            "left": {
                                "left": "A",
                                "operator": "AND",
                                "right": {
                                    "left": "C",
                                    "operator": "AND",
                                    "right": {"left": "D", "operator": "AND", "right": "F"},
                                },
                            },
                            "operator": "OR",
                            "right": {
                                "left": {
                                    "left": "B",
                                    "operator": "AND",
                                    "right": {
                                        "left": "C",
                                        "operator": "AND",
                                        "right": {"left": "D", "operator": "AND", "right": "F"},
                                    },
                                },
                                "operator": "OR",
                                "right": {
                                    "left": {
                                        "left": "A",
                                        "operator": "AND",
                                        "right": {
                                            "left": "C",
                                            "operator": "AND",
                                            "right": {"left": "E", "operator": "AND", "right": "G"},
                                        },
                                    },
                                    "operator": "OR",
                                    "right": {
                                        "left": {
                                            "left": "B",
                                            "operator": "AND",
                                            "right": {
                                                "left": "C",
                                                "operator": "AND",
                                                "right": {"left": "E", "operator": "AND", "right": "G"},
                                            },
                                        },
                                        "operator": "OR",
                                        "right": {
                                            "left": {
                                                "left": "A",
                                                "operator": "AND",
                                                "right": {
                                                    "left": "C",
                                                    "operator": "AND",
                                                    "right": {
                                                        "left": "D",
                                                        "operator": "AND",
                                                        "right": {"left": "H", "operator": "AND", "right": "I"},
                                                    },
                                                },
                                            },
                                            "operator": "OR",
                                            "right": {
                                                "left": "B",
                                                "operator": "AND",
                                                "right": {
                                                    "left": "C",
                                                    "operator": "AND",
                                                    "right": {
                                                        "left": "D",
                                                        "operator": "AND",
                                                        "right": {"left": "H", "operator": "AND", "right": "I"},
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "version": "v0.1",
                    },
                    "ip": "192.168.1.2/32",
                    "port": 53,
                    "metric": {"mlid": 223, "name": "dtwatcheddomain", "label": "Watched Domain"},
                    "triggeredFilters": [
                        {
                            "cfid": 156173,
                            "id": "A",
                            "filterType": "Watched endpoint source",
                            "arguments": {"value": ".+"},
                            "comparatorType": "does not match regular expression",
                            "trigger": {"value": ""},
                        },
                        {
                            "cfid": 156175,
                            "id": "C",
                            "filterType": "Direction",
                            "arguments": {"value": "out"},
                            "comparatorType": "is",
                            "trigger": {"value": "out"},
                        },
                        {
                            "cfid": 156177,
                            "id": "E",
                            "filterType": "Internal source device type",
                            "arguments": {"value": "12"},
                            "comparatorType": "is not",
                            "trigger": {"value": "6"},
                        },
                        {
                            "cfid": 156179,
                            "id": "G",
                            "filterType": "Destination port",
                            "arguments": {"value": 53},
                            "comparatorType": "=",
                            "trigger": {"value": "53"},
                        },
                        {
                            "cfid": 156180,
                            "id": "d1",
                            "filterType": "Internal source device type",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": "6"},
                        },
                        {
                            "cfid": 156181,
                            "id": "d10",
                            "filterType": "Watched endpoint description",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": ""},
                        },
                        {
                            "cfid": 156182,
                            "id": "d2",
                            "filterType": "Connection hostname",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": ""},
                        },
                        {
                            "cfid": 156183,
                            "id": "d3",
                            "filterType": "Destination IP",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": "192.168.1.2"},
                        },
                        {
                            "cfid": 156184,
                            "id": "d4",
                            "filterType": "ASN",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": ""},
                        },
                        {
                            "cfid": 156185,
                            "id": "d5",
                            "filterType": "Country",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": ""},
                        },
                        {
                            "cfid": 156186,
                            "id": "d6",
                            "filterType": "Message",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": "amazonlinux-2-repos-eu-west-2.s3.eu-west-2.amazonaws.com"},
                        },
                        {
                            "cfid": 156187,
                            "id": "d7",
                            "filterType": "Watched endpoint",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": "True"},
                        },
                        {
                            "cfid": 156188,
                            "id": "d8",
                            "filterType": "Watched endpoint source",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": ""},
                        },
                        {
                            "cfid": 156189,
                            "id": "d9",
                            "filterType": "Watched endpoint strength",
                            "arguments": {},
                            "comparatorType": "display",
                            "trigger": {"value": "100"},
                        },
                        {
                            "cfid": 156190,
                            "id": "H",
                            "filterType": "Internal destination",
                            "arguments": {},
                            "comparatorType": "is",
                            "trigger": {"value": "True"},
                        },
                        {
                            "cfid": 156191,
                            "id": "I",
                            "filterType": "Internal destination device type",
                            "arguments": {"value": "11"},
                            "comparatorType": "is not",
                            "trigger": {"value": "12"},
                        },
                    ],
                }
            ],
            "score": 0.541,
            "device": {
                "did": 6,
                "ip": "192.168.16.12345",
                "ips": [
                    {"ip": "192.168.16.#12345", "timems": 1687773600000, "time": "2023-06-26 10: 00: 00", "sid": 4}
                ],
                "sid": 4,
                "firstSeen": 1639068361000,
                "lastSeen": 1687774141000,
                "typename": "desktop",
                "typelabel": "Desktop",
            },
        }
    ]
    # flake8: qa


def test_next_batch(trigger, message1):
    with patch(
        "darktrace_modules.threat_visualizer_log_trigger.time"
    ) as mock_time, requests_mock.Mocker() as mock_request:
        last_ts = 1687774141.000
        batch_start = 1687774141.000
        batch_end = 1688465633.434
        mock_request.get(
            trigger.module.configuration.api_url + "/modelbreaches?starttime=1687770541000&includeallpinned=False",
            json=message1,
        )

        mock_time.time.side_effect = [batch_start, last_ts, batch_end]
        trigger.next_batch()

        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls[0]) == 1
        assert trigger.push_events_to_intakes.call_count == 1
