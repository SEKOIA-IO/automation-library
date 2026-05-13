import json
import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

package = ModuleType("connectors")
package.__path__ = [str(PROJECT_ROOT / "connectors")]
sys.modules["connectors"] = package
MoknLoginAttemptsTrigger = import_module("connectors.attempts").MoknLoginAttemptsTrigger
MoknLoginAttemptsTriggerConfiguration = import_module("connectors.configuration").MoknLoginAttemptsTriggerConfiguration
from mokn.domain import (
    AttemptCursor,
    AttemptQuery,
    MoknThreatLevel,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        """Mimic a successful requests response."""

    def json(self):
        """Return the mocked JSON payload."""
        return self._payload


def make_trigger(data_storage, **configuration_overrides):
    configuration = {
        "intake_key": "test-intake",
        "frequency": 60,
        "chunk_size": 100,
        "page_size": 100,
        "initial_lookback_minutes": 5,
        "statuses": [5, 9],
        "threat_levels": [MoknThreatLevel.HIGH],
        "pending": True,
    }
    configuration.update(configuration_overrides)
    trigger = object.__new__(MoknLoginAttemptsTrigger)
    trigger._configuration = MoknLoginAttemptsTriggerConfiguration.parse_obj(configuration)
    trigger.module = SimpleNamespace(
        configuration=SimpleNamespace(
            base_url="https://mokn.example",
            api_token="token",
            verify_ssl=False,
        )
    )
    trigger._data_path = Path(data_storage)
    trigger.log = Mock()
    trigger.push_events_to_intakes = Mock()
    trigger._stop_event = Mock()
    return trigger


def test_trigger_query_reflects_configuration(data_storage):
    trigger = make_trigger(
        data_storage,
        page_size=25,
        statuses=[1, 5],
        threat_levels=[MoknThreatLevel.MEDIUM],
        pending=False,
    )

    assert trigger.query == AttemptQuery(
        page_size=25,
        statuses=[1, 5],
        threat_levels=[MoknThreatLevel.MEDIUM],
        pending=False,
    )


def test_cursor_roundtrip_persists_seen_ids_for_same_second(data_storage):
    trigger = make_trigger(data_storage)
    cursor = AttemptCursor(
        second=datetime(2026, 4, 23, 8, 9, 10, 987654, tzinfo=UTC),
        seen_ids={7, 3},
    )

    trigger._set_cursor(cursor)
    restored = trigger._get_cursor()

    assert restored.second == datetime(2026, 4, 23, 8, 9, 10, tzinfo=UTC)
    assert restored.seen_ids == {3, 7}


def test_iterate_skips_seen_ids_and_updates_next_cursor(data_storage):
    trigger = make_trigger(data_storage)
    current_second = datetime(2026, 4, 23, 8, 9, 10, tzinfo=UTC)
    client = Mock()
    client.base_url = "https://mokn.example"
    client.request = Mock(
        side_effect=[
            FakeResponse(
                {
                    "status": "success",
                    "message": "Attempts successfully retrieved.",
                    "data": {
                        "results": [
                            {
                                "id": 1,
                                "updated_time": "2026-04-23T08:09:10+00:00",
                                "username": "seen-user",
                                "status": 5,
                            },
                            {
                                "id": 2,
                                "updated_time": "2026-04-23T08:09:10+00:00",
                                "username": "new-user",
                                "status": 9,
                                "is_targeted": True,
                                "ip": "127.0.0.1",
                                "country": "Germany",
                                "country_code": "DE",
                                "date": "2026-04-23T08:09:10+00:00",
                                "bait_name": "App Portal",
                                "password": "password-example",
                                "comment": "",
                                "type": "Targeted",
                                "identification": "App Connector",
                                "threat_level": "LOW",
                            },
                        ]
                    },
                }
            ),
            FakeResponse(
                {
                    "status": "success",
                    "message": "Attempts successfully retrieved.",
                    "data": {
                        "attack": {
                            "ip": "127.0.0.1",
                            "country": "Germany",
                            "country_code": "DE",
                            "username": "hidden-user",
                            "password": "hidden-password",
                            "ja4h": "sample-ja4h",
                            "user_agent": "GenericBrowser/1.0",
                            "headers": [
                                ["Host", "app"],
                                ["Origin", "https://app"],
                                ["Referer", "https://app/login"],
                                ["X-Forwarded-For", "127.0.0.1"],
                            ],
                            "date": "2026-04-23T08:09:10+00:00",
                            "bait": "App Portal",
                            "threat_level": "LOW",
                            "opportunistic_patterns": [
                                {
                                    "name": "has_leaked",
                                    "threat_level_setting": "HIGH",
                                }
                            ],
                        },
                        "credential_checks": [],
                        "leaks": [],
                        "comment": None,
                        "attacker_profile": {
                            "reputation": "Unknown",
                            "total_attempts": 3,
                            "total_targeted_attempts": 1,
                        },
                    },
                }
            ),
        ]
    )
    trigger.__dict__["client"] = client

    batches = list(trigger.iterate(AttemptCursor(second=current_second, seen_ids={1})))

    assert batches == [
        (
            [
                {
                    "event_type": "mokn_bait_attempt",
                    "id": 2,
                    "updated_time": "2026-04-23T08:09:10+00:00",
                    "username": "new-user",
                    "status": 9,
                    "is_targeted": True,
                    "date": "2026-04-23T08:09:10+00:00",
                    "bait_name": "App Portal",
                    "password": "password-example",
                    "comment": "",
                    "type": "Targeted",
                    "identification": "App Connector",
                    "threat_level": "LOW",
                    "attack": {
                        "ip": "127.0.0.1",
                        "country": "Germany",
                        "country_code": "DE",
                        "ja4h": "sample-ja4h",
                        "user_agent": "GenericBrowser/1.0",
                        "headers": [
                            ["Host", "app"],
                            ["Origin", "https://app"],
                            ["Referer", "https://app/login"],
                            ["X-Forwarded-For", "127.0.0.1"],
                        ],
                        "opportunistic_patterns": [
                            {
                                "name": "has_leaked",
                                "threat_level_setting": "HIGH",
                            }
                        ],
                        "reputation": "Unknown",
                        "total_attempts": 3,
                        "total_targeted_attempts": 1,
                    },
                }
            ],
            current_second,
        )
    ]
    assert trigger._next_cursor.second == current_second
    assert trigger._next_cursor.seen_ids == {1, 2}


def test_next_run_pushes_events_and_updates_checkpoint(data_storage):
    trigger = make_trigger(data_storage)
    initial_cursor = AttemptCursor(
        second=datetime(2026, 4, 23, 8, 9, 10, tzinfo=UTC),
        seen_ids=set(),
    )
    next_cursor = AttemptCursor(
        second=datetime(2026, 4, 23, 8, 9, 11, tzinfo=UTC),
        seen_ids={42},
    )
    trigger._get_cursor = Mock(return_value=initial_cursor)
    trigger._set_cursor = Mock()
    client = Mock()
    client.base_url = "https://mokn.example"
    client.request = Mock(
        side_effect=[
            FakeResponse(
                {
                    "status": "success",
                    "message": "Attempts successfully retrieved.",
                    "data": {
                        "results": [
                            {
                                "id": 42,
                                "updated_time": "2026-04-23T08:09:11+00:00",
                                "username": "user-42",
                                "status": 5,
                                "is_targeted": False,
                                "ip": "127.0.0.1",
                                "country": "France",
                                "country_code": "FR",
                                "date": "2026-04-23T08:09:11+00:00",
                                "bait_name": "App Portal",
                                "password": "password-42",
                                "comment": "",
                                "type": "Bots",
                                "identification": "",
                                "threat_level": "LOW",
                            }
                        ]
                    },
                }
            ),
            FakeResponse(
                {
                    "status": "success",
                    "message": "Attempts successfully retrieved.",
                    "data": {
                        "attack": {
                            "ip": "127.0.0.1",
                            "country": "France",
                            "country_code": "FR",
                            "username": "hidden-user",
                            "password": "hidden-password",
                            "ja4h": "sample-ja4h",
                            "user_agent": "GenericBrowser/1.0",
                            "headers": [
                                ["Host", "app"],
                                ["Origin", "https://app"],
                                ["Referer", "https://app/login"],
                                ["X-Forwarded-For", "127.0.0.1"],
                            ],
                            "date": "2026-04-23T08:09:11+00:00",
                            "bait": "App Portal",
                            "threat_level": "LOW",
                            "opportunistic_patterns": [
                                {
                                    "name": "has_leaked",
                                    "threat_level_setting": "HIGH",
                                }
                            ],
                        },
                        "credential_checks": [],
                        "leaks": [],
                        "comment": None,
                        "attacker_profile": {
                            "reputation": "Unknown",
                            "total_attempts": 4,
                            "total_targeted_attempts": 1,
                        },
                    },
                }
            ),
        ]
    )
    trigger.__dict__["client"] = client

    trigger.next_run()

    trigger.push_events_to_intakes.assert_called_once_with(
        events=[
            json.dumps(
                {
                    "event_type": "mokn_bait_attempt",
                    "id": 42,
                    "updated_time": "2026-04-23T08:09:11+00:00",
                    "username": "user-42",
                    "status": 5,
                    "is_targeted": False,
                    "date": "2026-04-23T08:09:11+00:00",
                    "bait_name": "App Portal",
                    "password": "password-42",
                    "comment": "",
                    "type": "Bots",
                    "identification": "",
                    "threat_level": "LOW",
                    "attack": {
                        "ip": "127.0.0.1",
                        "country": "France",
                        "country_code": "FR",
                        "ja4h": "sample-ja4h",
                        "user_agent": "GenericBrowser/1.0",
                        "headers": [
                            ["Host", "app"],
                            ["Origin", "https://app"],
                            ["Referer", "https://app/login"],
                            ["X-Forwarded-For", "127.0.0.1"],
                        ],
                        "opportunistic_patterns": [
                            {
                                "name": "has_leaked",
                                "threat_level_setting": "HIGH",
                            }
                        ],
                        "reputation": "Unknown",
                        "total_attempts": 4,
                        "total_targeted_attempts": 1,
                    },
                }
            )
        ]
    )
    trigger._set_cursor.assert_called_once_with(next_cursor)


def test_next_run_chunks_events_according_to_chunk_size(data_storage):
    trigger = make_trigger(data_storage, chunk_size=2)
    cursor = AttemptCursor(
        second=datetime(2026, 4, 23, 8, 9, 10, tzinfo=UTC),
        seen_ids=set(),
    )
    trigger._get_cursor = Mock(return_value=cursor)
    trigger._set_cursor = Mock()

    def make_summary(attempt_id: int):
        return {
            "id": attempt_id,
            "updated_time": "2026-04-23T08:09:11+00:00",
            "username": f"user-{attempt_id}",
            "status": 5,
            "is_targeted": False,
            "ip": "1.2.3.4",
            "country": "France",
            "country_code": "FR",
            "date": "2026-04-23T08:09:11+00:00",
            "bait_name": "App Portal",
            "password": "pw",
            "comment": "",
            "type": "Bots",
            "identification": "",
            "threat_level": "LOW",
        }

    detail_response = {
        "status": "success",
        "message": "ok",
        "data": {
            "attack": {
                "ip": "1.2.3.4",
                "country": "France",
                "country_code": "FR",
                "username": "u",
                "password": "p",
                "ja4h": "",
                "user_agent": "Bot/1.0",
                "headers": [],
                "date": "2026-04-23T08:09:11+00:00",
                "bait": "App Portal",
                "threat_level": "LOW",
                "opportunistic_patterns": [],
            },
            "credential_checks": [],
            "leaks": [],
            "comment": None,
            "attacker_profile": {"reputation": "Unknown", "total_attempts": 1, "total_targeted_attempts": 0},
        },
    }

    client = Mock()
    client.base_url = "https://mokn.example"
    client.request = Mock(
        side_effect=[
            FakeResponse(
                {
                    "status": "success",
                    "message": "ok",
                    "data": {"results": [make_summary(i) for i in range(1, 4)]},
                }
            ),
            FakeResponse(detail_response),
            FakeResponse(detail_response),
            FakeResponse(detail_response),
            FakeResponse({"status": "success", "message": "ok", "data": {"results": []}}),
        ]
    )
    trigger.__dict__["client"] = client

    trigger.next_run()

    assert trigger.push_events_to_intakes.call_count == 2
    first_call_events = trigger.push_events_to_intakes.call_args_list[0].kwargs["events"]
    second_call_events = trigger.push_events_to_intakes.call_args_list[1].kwargs["events"]
    assert len(first_call_events) == 2
    assert len(second_call_events) == 1


def test_next_run_waits_when_no_events_are_fetched(data_storage):
    trigger = make_trigger(data_storage, frequency=10)
    cursor = AttemptCursor(
        second=datetime(2026, 4, 23, 8, 9, 10, tzinfo=UTC),
        seen_ids=set(),
    )
    trigger._get_cursor = Mock(return_value=cursor)
    client = Mock()
    client.base_url = "https://mokn.example"
    client.request = Mock(
        return_value=FakeResponse(
            {
                "status": "success",
                "message": "Attempts successfully retrieved.",
                "data": {"results": []},
            }
        )
    )
    trigger.__dict__["client"] = client

    trigger.next_run()

    trigger.push_events_to_intakes.assert_not_called()
    trigger._stop_event.wait.assert_called_once()
