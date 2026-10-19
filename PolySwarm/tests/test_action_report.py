import json
from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions
from requests import RequestException

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_report import Report
from tests.helpers import autospec_build_client

# Real report bodies, trimmed for size, captured live from PolySwarm for a
# current malicious artifact (a cryptominer dropped by a fake WinZip
# installer, contacting auto.alphapool.tech) through both sandbox providers.
# Field names, nesting and values below are exactly what the API returned;
# nothing here is invented. The full untrimmed captures this was cut from
# are the CAPE and Triage sandbox reports for sha256
# 6e774dc769bcf252fdba22a45fe3f55b701e8d53fa61525a26c255b10cfa2aa9.

CAPE_REPORT = json.loads(r"""
{
  "malware_family": [],
  "ttp": [],
  "signature_names": [
    "antivm_checks_available_memory",
    "queries_computer_name",
    "queries_user_name",
    "queries_keyboard_layout",
    "antidebug_setunhandledexceptionfilter",
    "stealth_timeout"
  ],
  "network": {
    "hosts": [
      {
        "asn": "",
        "asn_name": "",
        "country_name": "unknown",
        "hostname": "doxbin.cy",
        "inaddrarpa": "",
        "ip": "172.67.173.197",
        "ports": []
      }
    ],
    "domains": [
      {
        "domain": "doxbin.cy",
        "ip": "172.67.173.197"
      }
    ],
    "dns": [
      {
        "answers": [
          {"data": "172.67.173.197", "type": "A"},
          {"data": "104.21.55.221", "type": "A"}
        ],
        "first_seen": 1790043674.579611,
        "request": "doxbin.cy",
        "type": "A"
      }
    ],
    "http": []
  },
  "dropped": [],
  "behavior": {
    "processes": [
      {
        "environ": {
          "CommandLine": "\"C:\\Users\\maxine\\AppData\\Local\\Temp\\winzip.exe\" ",
          "UserName": "maxine"
        },
        "module_path": "C:\\Users\\maxine\\AppData\\Local\\Temp\\winzip.exe",
        "parent_id": 2148,
        "process_id": 3320,
        "process_name": "winzip.exe"
      },
      {
        "environ": {
          "CommandLine": "\"C:\\Users\\maxine\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe\"",
          "UserName": "maxine"
        },
        "module_path": "C:\\Users\\maxine\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe",
        "parent_id": 3320,
        "process_id": 6316,
        "process_name": "RuntimeBroker.exe"
      }
    ]
  }
}
""")

TRIAGE_REPORT = json.loads(r"""
{
  "malware_family": [],
  "ttp": ["T1012", "T1497", "T1012", "T1497", "T1012", "T1082", "T1547.001", "T1112", "T1012", "T1082"],
  "static": {
    "signatures": [
      {
        "desc": "Checks for missing Authenticode signature.",
        "indicators": [{"resource": "acrord32.exe"}],
        "label": "unsigned_pe",
        "name": "Unsigned PE",
        "score": 3
      }
    ]
  },
  "targets": [
    {
      "signatures": [
        {
          "indicators": [
            {
              "description": "Key opened",
              "ioc": "\\REGISTRY\\MACHINE\\SOFTWARE\\Oracle\\VirtualBox Guest Additions",
              "procid": 76
            }
          ],
          "label": "identifies_vbox_guestadditions_reg",
          "name": "Looks for VirtualBox Guest Additions in registry",
          "score": 9,
          "tags": ["defense_evasion"],
          "ttp": ["T1012", "T1497"]
        },
        {
          "indicators": [
            {
              "description": "Key opened",
              "ioc": "\\REGISTRY\\MACHINE\\SOFTWARE\\VMware, Inc.\\VMware Tools",
              "procid": 76
            }
          ],
          "label": "identifies_vmware_tools_reg",
          "name": "Looks for VMWare Tools registry key",
          "score": 8,
          "tags": ["defense_evasion"],
          "ttp": ["T1012", "T1497"]
        }
      ]
    }
  ],
  "network": {
    "flows": [
      {"domain": "doxbin.cy", "dst": "188.114.97.0:2083", "id": 3, "proto": "tcp", "tls_sni": "doxbin.cy"},
      {"domain": "doxbin.cy", "dst": "188.114.97.0:2083", "id": 4, "proto": "tcp", "tls_sni": "doxbin.cy"}
    ],
    "ips": [
      {"asn": "AS8075", "cc": "US", "ip": "150.171.110.147"},
      {"asn": "AS13335", "cc": "US", "ip": "188.114.97.0"},
      {"asn": "AS8075", "cc": "US", "ip": "4.150.223.106"},
      {"asn": "AS15169", "cc": "US", "ip": "8.8.8.8"},
      {"asn": "AS199524", "cc": "NL", "ip": "93.123.17.252"}
    ]
  },
  "requests": [
    {"dns_request": [], "dns_response": [], "domain": "doxbin.cy", "http_request": [], "http_response": []}
  ],
  "processes": [
    {
      "cmd": "\"C:\\Users\\Admin\\AppData\\Local\\Temp\\acrord32.exe\"",
      "image": "C:\\Users\\Admin\\AppData\\Local\\Temp\\acrord32.exe",
      "pid": 2580,
      "ppid": 2448
    },
    {
      "cmd": "\"C:\\Users\\Admin\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe\"",
      "image": "C:\\Users\\Admin\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe",
      "pid": 1388,
      "ppid": 2580
    }
  ],
  "dumped": [
    {
      "kind": "martian",
      "name": "files/0x000100000002992d-18.dat",
      "origin": "imgload",
      "path": "C:\\Users\\Admin\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe",
      "sha256": "a861267f02af6a092d543f0334767a1a438943835dd3a62e92a346430c5284d3"
    },
    {
      "kind": "martian",
      "name": "files/0x0001000000029929-20.dat",
      "origin": "imgload",
      "path": "C:\\Users\\Admin\\AppData\\Local\\WindowsRecovery\\Update.exe",
      "sha256": "6e774dc769bcf252fdba22a45fe3f55b701e8d53fa61525a26c255b10cfa2aa9"
    }
  ]
}
""")


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> Report:
    return Report(module=module, data_path=data_storage)


def _make_sandbox_artifact(
    *,
    artifact_id: str = "art-1",
    instance_id: str = "inst-1",
    name: str = "dropped.dll",
    artifact_type: str = "dropped_file",
    mimetype: str = "application/x-dosexec",
) -> MagicMock:
    a = MagicMock()
    a.id = artifact_id
    a.instance_id = instance_id
    a.name = name
    a.type = artifact_type
    a.mimetype = mimetype
    return a


def _make_sandbox_task(
    *,
    task_id: str = "task-123",
    sha256: str = "aa" * 32,
    sandbox: str = "cape",
    status: str = "SUCCEEDED",
    report: dict | None = None,
    config: dict | None = None,
    sandbox_artifacts: list[MagicMock] | None = None,
) -> MagicMock:
    if sandbox_artifacts is None:
        sandbox_artifacts = [_make_sandbox_artifact()]

    task = MagicMock()
    task.id = task_id
    task.sha256 = sha256
    task.sandbox = sandbox
    task.status = status
    task.report = report
    task.config = config if config is not None else {}
    task.sandbox_artifacts = sandbox_artifacts
    return task


# --- Typed fields from real captured payloads -------------------------------


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_typed_fields_from_real_cape_payload(mock_build_client: MagicMock, action: Report) -> None:
    task = _make_sandbox_task(
        sandbox="cape",
        report=CAPE_REPORT,
        config={"cape_malscore": 6.0},
    )
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32, "sandbox": "cape"})
    assert response is not None

    assert response["malicious"] is True
    behavior = response["behavior"]
    assert behavior["behavior_signatures"] == [
        "antivm_checks_available_memory",
        "queries_computer_name",
        "queries_user_name",
        "queries_keyboard_layout",
        "antidebug_setunhandledexceptionfilter",
        "stealth_timeout",
    ]
    assert behavior["mitre_techniques"] == []
    assert behavior["contacted_hosts"] == ["172.67.173.197"]
    assert behavior["contacted_domains"] == ["doxbin.cy"]
    assert behavior["contacted_urls"] == []
    assert behavior["dropped_file_hashes"] == []
    assert behavior["processes"] == [
        {
            "pid": 3320,
            "parent_pid": 2148,
            "image": "C:\\Users\\maxine\\AppData\\Local\\Temp\\winzip.exe",
            "command_line": '"C:\\Users\\maxine\\AppData\\Local\\Temp\\winzip.exe" ',
        },
        {
            "pid": 6316,
            "parent_pid": 3320,
            "image": "C:\\Users\\maxine\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe",
            "command_line": '"C:\\Users\\maxine\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe"',
        },
    ]


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_typed_fields_from_real_triage_payload(mock_build_client: MagicMock, action: Report) -> None:
    task = _make_sandbox_task(
        sandbox="triage",
        report=TRIAGE_REPORT,
        config={"traige_analysis_score": 9},
    )
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32, "sandbox": "triage"})
    assert response is not None

    assert response["malicious"] is True
    behavior = response["behavior"]
    # Static PE checks and dynamic technique-linked signatures both fold into
    # the same behavior_signatures list Triage has no flat equivalent for.
    assert behavior["behavior_signatures"] == [
        "Unsigned PE",
        "Looks for VirtualBox Guest Additions in registry",
        "Looks for VMWare Tools registry key",
    ]
    # The top-level ttp list repeats an id once per signature that raised
    # it; dedup collapses that back to the distinct techniques observed.
    assert behavior["mitre_techniques"] == ["T1012", "T1497", "T1082", "T1547.001", "T1112"]
    assert behavior["contacted_hosts"] == [
        "150.171.110.147",
        "188.114.97.0",
        "4.150.223.106",
        "8.8.8.8",
        "93.123.17.252",
    ]
    assert behavior["contacted_domains"] == ["doxbin.cy"]
    assert behavior["contacted_urls"] == []
    assert behavior["dropped_file_hashes"] == [
        "a861267f02af6a092d543f0334767a1a438943835dd3a62e92a346430c5284d3",
        "6e774dc769bcf252fdba22a45fe3f55b701e8d53fa61525a26c255b10cfa2aa9",
    ]
    assert behavior["processes"] == [
        {
            "pid": 2580,
            "parent_pid": 2448,
            "image": "C:\\Users\\Admin\\AppData\\Local\\Temp\\acrord32.exe",
            "command_line": '"C:\\Users\\Admin\\AppData\\Local\\Temp\\acrord32.exe"',
        },
        {
            "pid": 1388,
            "parent_pid": 2580,
            "image": "C:\\Users\\Admin\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe",
            "command_line": '"C:\\Users\\Admin\\AppData\\Roaming\\WindowsFramehost\\RuntimeBroker.exe"',
        },
    ]


# --- Fetch-only: no file argument, no submission ----------------------------


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_returns_existing_report(mock_build_client: MagicMock, action: Report) -> None:
    existing_task = _make_sandbox_task(config={"cape_malscore": 6.0}, report=CAPE_REPORT)
    mock_build_client.return_value.sandbox_task_latest.return_value = existing_task

    response = action.run({"sha256": "aa" * 32})
    assert response is not None

    mock_build_client.return_value.sandbox_task_latest.assert_called_once_with("aa" * 32, sandbox="cape")
    assert response["sandbox_task_id"] == "task-123"
    assert response["status"] == "SUCCEEDED"
    assert response["report"] == CAPE_REPORT


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_file_argument_is_ignored_and_never_triggers_submission(mock_build_client: MagicMock, action: Report) -> None:
    """The submission argument is gone entirely. A stray 'file' key from an old playbook call is silently
    dropped by the arguments model (it has no such field) and never causes a submission.
    """
    task = _make_sandbox_task(config={"cape_malscore": 1.0}, report=CAPE_REPORT)
    mock_api = mock_build_client.return_value
    mock_api.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32, "file": "sample.exe"})
    assert response is not None
    assert response["report"] == CAPE_REPORT
    mock_api.sandbox_file.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_no_submission_method_ever_called(mock_build_client: MagicMock, action: Report) -> None:
    """There is no submission path left in this action at all: sandbox_file is never called, even when
    nothing has ever been detonated for this hash.
    """
    mock_api = mock_build_client.return_value
    mock_api.sandbox_task_latest.side_effect = ps_exceptions.NoResultsException("no results")

    response = action.run({"sha256": "aa" * 32})
    assert response is not None
    assert response["status"] == "NOT_FOUND"
    mock_api.sandbox_file.assert_not_called()


# --- No report available: nothing has ever been detonated ------------------


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_no_report_available_when_nothing_ever_detonated(mock_build_client: MagicMock, action: Report) -> None:
    mock_build_client.return_value.sandbox_task_latest.side_effect = ps_exceptions.NoResultsException("no results")

    response = action.run({"sha256": "aa" * 32, "sandbox": "cape"})
    assert response is not None

    assert response["status"] == "NOT_FOUND"
    assert response["malicious"] is None
    assert response["sandbox_task_id"] == ""
    assert response["sha256"] == "aa" * 32
    assert response["sandbox"] == "cape"
    assert response["report"] is None
    assert response["behavior"]["behavior_signatures"] == []


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_not_found_exception_also_yields_no_report_available(mock_build_client: MagicMock, action: Report) -> None:
    mock_build_client.return_value.sandbox_task_latest.side_effect = ps_exceptions.NotFoundException("not found")

    response = action.run({"sha256": "aa" * 32})
    assert response is not None
    assert response["status"] == "NOT_FOUND"
    assert response["malicious"] is None


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_reports_sandbox_failure_as_no_report_branch(mock_build_client: MagicMock, action: Report) -> None:
    failed_task = _make_sandbox_task(status="FAILED", report=None)
    mock_build_client.return_value.sandbox_task_latest.return_value = failed_task

    response = action.run({"sha256": "aa" * 32})
    assert response is not None

    assert action._error is None
    assert response["status"] == "FAILED"
    assert response["malicious"] is None
    assert response["report"] is None


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_succeeded_with_empty_report_is_no_report_branch(mock_build_client: MagicMock, action: Report) -> None:
    task = _make_sandbox_task(status="SUCCEEDED", report=None)
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32})
    assert response is not None
    assert response["malicious"] is None
    assert response["status"] == "SUCCEEDED"


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_still_running_with_no_wait_requested_is_no_report_branch(
    mock_build_client: MagicMock, action: Report
) -> None:
    """Default max_wait_seconds is 0: a task already running is reported as no report available
    immediately, without ever polling for status again.
    """
    mock_api = mock_build_client.return_value
    running_task = _make_sandbox_task(status="RUNNING", report=None)
    mock_api.sandbox_task_latest.return_value = running_task

    response = action.run({"sha256": "aa" * 32})
    assert response is not None

    mock_api.sandbox_task_status.assert_not_called()
    assert response["status"] == "RUNNING"
    assert response["malicious"] is None


# --- Not malicious branch --------------------------------------------------


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_not_malicious_when_provider_score_is_zero(mock_build_client: MagicMock, action: Report) -> None:
    clean_report = {
        "malware_family": [],
        "ttp": [],
        "signature_names": [],
        "network": {},
        "dropped": [],
        "behavior": {},
    }
    task = _make_sandbox_task(report=clean_report, config={"cape_malscore": 0.0})
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32})
    assert response is not None
    assert response["malicious"] is False


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_malicious_fallback_when_provider_score_absent(mock_build_client: MagicMock, action: Report) -> None:
    # Neither cape_malscore nor a triage score key is present on this task's
    # config; the malware family PolySwarm still identified stands in for a
    # numeric score that was never supplied.
    report = {
        "malware_family": ["Emotet"],
        "ttp": [],
        "signature_names": [],
        "network": {},
        "dropped": [],
        "behavior": {},
    }
    task = _make_sandbox_task(sandbox="cape", report=report, config={})
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32, "sandbox": "cape"})
    assert response is not None
    assert response["malicious"] is True


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_network_urls_captured_when_provider_supplies_one(mock_build_client: MagicMock, action: Report) -> None:
    cape_with_http = {
        "malware_family": [],
        "ttp": [],
        "signature_names": [],
        "network": {
            "hosts": [],
            "domains": [],
            "dns": [],
            "http": [{"uri": "http://doxbin.cy/gate.php"}],
        },
        "dropped": [],
        "behavior": {},
    }
    task = _make_sandbox_task(sandbox="cape", report=cape_with_http, config={"cape_malscore": 2.0})
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32, "sandbox": "cape"})
    assert response is not None
    assert response["behavior"]["contacted_urls"] == ["http://doxbin.cy/gate.php"]

    triage_with_http = {
        "malware_family": [],
        "ttp": [],
        "static": {"signatures": []},
        "targets": [],
        "network": {"flows": [], "ips": []},
        "requests": [
            {
                "domain": "doxbin.cy",
                "dns_request": [],
                "dns_response": [],
                "http_request": [{"url": "http://doxbin.cy/gate.php"}],
                "http_response": [],
            }
        ],
        "processes": [],
        "dumped": [],
    }
    task2 = _make_sandbox_task(sandbox="triage", report=triage_with_http, config={"traige_analysis_score": 2})
    mock_build_client.return_value.sandbox_task_latest.return_value = task2

    response2 = action.run({"sha256": "aa" * 32, "sandbox": "triage"})
    assert response2 is not None
    assert response2["behavior"]["contacted_urls"] == ["http://doxbin.cy/gate.php"]


# --- Waiting for a detonation already running elsewhere ---------------------


@patch("polyswarm_modules.sandbox.time", autospec=True)
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_waits_for_already_running_detonation_with_exponential_backoff(
    mock_build_client: MagicMock, mock_time: MagicMock, action: Report
) -> None:
    mock_time.monotonic.return_value = 0.0
    mock_api = mock_build_client.return_value
    running_task = _make_sandbox_task(status="RUNNING", report=None)
    mock_api.sandbox_task_latest.return_value = running_task

    running = [_make_sandbox_task(status="RUNNING") for _ in range(4)]
    done = _make_sandbox_task(status="SUCCEEDED", report=CAPE_REPORT, config={"cape_malscore": 6.0})
    mock_api.sandbox_task_status.side_effect = [*running, done]

    response = action.run({"sha256": "aa" * 32, "sandbox": "cape", "max_wait_seconds": 300})
    assert response is not None

    assert mock_api.sandbox_task_status.call_count == 5
    sleep_calls = [call.args[0] for call in mock_time.sleep.call_args_list]
    # Interval doubles from a 5 second first check up to a 60 second ceiling.
    assert sleep_calls == [5.0, 10.0, 20.0, 40.0, 60.0]
    assert response["status"] == "SUCCEEDED"
    assert response["malicious"] is True


@patch("polyswarm_modules.sandbox.time", autospec=True)
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_wait_hits_ceiling_still_running_yields_no_report(
    mock_build_client: MagicMock, mock_time: MagicMock, action: Report
) -> None:
    # The deadline is computed once from the first monotonic() call; the
    # second call (the first loop check) already reads past it, so the
    # task never gets polled again and is reported as still processing.
    mock_time.monotonic.side_effect = [0.0, 10.0]
    mock_api = mock_build_client.return_value
    running_task = _make_sandbox_task(status="RUNNING", report=None)
    mock_api.sandbox_task_latest.return_value = running_task

    response = action.run({"sha256": "aa" * 32, "sandbox": "cape", "max_wait_seconds": 1})
    assert response is not None

    mock_api.sandbox_task_status.assert_not_called()
    mock_time.sleep.assert_not_called()
    assert response["status"] == "RUNNING"
    assert response["malicious"] is None
    assert response["behavior"]["behavior_signatures"] == []


@patch("polyswarm_modules.sandbox.time", autospec=True)
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_status_check_error_during_wait_retries(
    mock_build_client: MagicMock, mock_time: MagicMock, action: Report
) -> None:
    mock_time.monotonic.return_value = 0.0
    mock_api = mock_build_client.return_value
    running_task = _make_sandbox_task(status="RUNNING", report=None)
    mock_api.sandbox_task_latest.return_value = running_task

    done = _make_sandbox_task(status="SUCCEEDED", report=CAPE_REPORT, config={"cape_malscore": 1.0})
    # A transient failure checking status is swallowed and retried on the
    # next poll rather than failing the whole action.
    mock_api.sandbox_task_status.side_effect = [
        RequestException("https://api.polyswarm.network/?key=SECRETVALUE"),
        done,
    ]

    response = action.run({"sha256": "aa" * 32, "sandbox": "cape", "max_wait_seconds": 300})

    assert response is not None
    assert action._error is None
    assert mock_api.sandbox_task_status.call_count == 2


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_no_wait_never_calls_status_check(mock_build_client: MagicMock, action: Report) -> None:
    """max_wait_seconds=0 (the default) must never poll at all, even when the task is not terminal."""
    mock_api = mock_build_client.return_value
    running_task = _make_sandbox_task(status="PENDING", report=None)
    mock_api.sandbox_task_latest.return_value = running_task

    response = action.run({"sha256": "aa" * 32, "sandbox": "cape", "max_wait_seconds": 0})
    assert response is not None

    mock_api.sandbox_task_status.assert_not_called()
    assert response["status"] == "PENDING"


# --- Usage errors: return None, message never quotes the client -----------


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_client_error_looking_up_report_returns_none_with_safe_message(
    mock_build_client: MagicMock, action: Report
) -> None:
    mock_build_client.return_value.sandbox_task_latest.side_effect = RequestException(
        "https://api.polyswarm.network/?key=SECRETVALUE"
    )

    response = action.run({"sha256": "aa" * 32})

    assert response is None
    assert action._error is not None
    assert "SECRETVALUE" not in action._error
    assert "RequestException" in action._error


# --- bounded wait and hash validation ---


def test_a_wait_beyond_the_ceiling_is_rejected(action: Report) -> None:
    response = action.run({"sha256": "aa" * 32, "max_wait_seconds": 301})
    assert response is None
    assert action.error_message is not None
    assert "max_wait_seconds" in action.error_message


@pytest.mark.parametrize("value", ["not-a-hash", "zz" * 32, "", "aa" * 16, "aa" * 20])
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_a_malformed_or_short_hash_is_refused_before_any_request(
    mock_build_client: MagicMock, action: Report, value: str
) -> None:
    response = action.run({"sha256": value})

    assert response is None
    assert action._error is not None
    assert "Refusing" in action._error
    mock_build_client.assert_not_called()


# --- Score thresholds --------------------------------------------------------


def _verdict_for(mock_build_client: MagicMock, action: Report, sandbox: str, config: dict, report: dict | None = None):
    clean = {"malware_family": [], "ttp": [], "signature_names": ["queries_computer_name"], "network": {}}
    task = _make_sandbox_task(sandbox=sandbox, report=report or clean, config=config)
    mock_build_client.return_value.sandbox_task_latest.return_value = task
    response = action.run({"sha256": "aa" * 32, "sandbox": sandbox})
    assert response is not None
    return response["malicious"]


@pytest.mark.parametrize("score", [1, 3, 6, "1", 6.9, 7, 7.9, "7"])
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_triage_scores_below_the_malicious_band_are_not_malicious(
    mock_build_client: MagicMock, action: Report, score: object
) -> None:
    """Triage calls 5 to 7 suspicious, with common benign causes, so 7 is not a verdict."""
    assert _verdict_for(mock_build_client, action, "triage", {"traige_analysis_score": score}) is False


@pytest.mark.parametrize("score", [8, 9, 10, "9"])
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_high_triage_scores_are_malicious(mock_build_client: MagicMock, action: Report, score: object) -> None:
    """Triage puts 8 and 9 at likely malicious and 10 at a named family."""
    assert _verdict_for(mock_build_client, action, "triage", {"traige_analysis_score": score}) is True


@pytest.mark.parametrize("key", ["traige_analysis_score", "triage_analysis_score"])
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_either_spelling_of_the_dynamic_triage_key_is_read(
    mock_build_client: MagicMock, action: Report, key: str
) -> None:
    """Reading only one spelling would fall through to the static score on every detonation."""
    assert _verdict_for(mock_build_client, action, "triage", {key: 9}) is True


@pytest.mark.parametrize("score", [0.5, 1.0, 2.5, 5.9, "3.0"])
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_low_cape_scores_are_not_malicious(mock_build_client: MagicMock, action: Report, score: object) -> None:
    assert _verdict_for(mock_build_client, action, "cape", {"cape_malscore": score}) is False


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_the_captured_malicious_cape_score_is_malicious(mock_build_client: MagicMock, action: Report) -> None:
    assert _verdict_for(mock_build_client, action, "cape", {"cape_malscore": 6.0}, CAPE_REPORT) is True


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_triage_static_score_is_used_when_the_dynamic_score_is_absent(
    mock_build_client: MagicMock, action: Report
) -> None:
    assert _verdict_for(mock_build_client, action, "triage", {"triage_static_score": 1}) is False


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_an_unreadable_score_does_not_raise_and_is_not_a_clean_verdict(
    mock_build_client: MagicMock, action: Report
) -> None:
    assert _verdict_for(mock_build_client, action, "cape", {"cape_malscore": "n/a"}) is None


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_signatures_alone_never_make_a_report_malicious_or_clean(mock_build_client: MagicMock, action: Report) -> None:
    assert _verdict_for(mock_build_client, action, "cape", {}, CAPE_REPORT) is None


# --- Unscored reports are not clean reports -----------------------------------

_NO_FAMILY_REPORT = {"malware_family": [], "ttp": [], "signature_names": ["queries_computer_name"], "network": {}}


def _assert_unscored(response: dict, action: Report) -> None:
    assert response["status"] == "SUCCEEDED"
    assert response["malicious"] is None
    assert response["unscored"] is True
    assert action._outputs == {"no report available": True}
    assert "not malicious" not in action._outputs
    # The evidence is still handed over for an analyst.
    assert response["report"] == _NO_FAMILY_REPORT


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_a_succeeded_report_with_no_score_and_no_family_is_not_a_clean_verdict(
    mock_build_client: MagicMock, action: Report
) -> None:
    task = _make_sandbox_task(sandbox="cape", report=_NO_FAMILY_REPORT, config={})
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32})
    assert response is not None
    _assert_unscored(response, action)


@pytest.mark.parametrize(
    ("sandbox", "config"),
    [
        ("cape", None),
        ("cape", {"cape_malscore": None}),
        ("cape", {"cape_malscore": "n/a"}),
        ("cape", {"triage_static_score": 9}),
        ("triage", {}),
        ("triage", {"traige_analysis_score": None, "triage_analysis_score": None, "triage_static_score": None}),
        ("triage", {"traige_analysis_score": "n/a"}),
        ("triage", {"cape_malscore": 9}),
        ("other", {"cape_malscore": 9, "traige_analysis_score": 9}),
    ],
)
@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_each_cause_of_a_missing_score_reads_as_unscored_not_clean(
    mock_build_client: MagicMock, action: Report, sandbox: str, config: dict | None
) -> None:
    task = _make_sandbox_task(sandbox=sandbox, report=_NO_FAMILY_REPORT)
    task.config = config
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32, "sandbox": sandbox})
    assert response is not None
    _assert_unscored(response, action)


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_a_scored_clean_report_is_still_not_malicious_and_not_unscored(
    mock_build_client: MagicMock, action: Report
) -> None:
    task = _make_sandbox_task(sandbox="cape", report=_NO_FAMILY_REPORT, config={"cape_malscore": 0.5})
    mock_build_client.return_value.sandbox_task_latest.return_value = task

    response = action.run({"sha256": "aa" * 32})
    assert response is not None
    assert response["malicious"] is False
    assert response["unscored"] is False
    assert action._outputs == {"not malicious": True}


# --- include_raw_report -------------------------------------------------------


def _run_with_flag(mock_build_client: MagicMock, action: Report, task: MagicMock, **extra: object) -> dict:
    mock_build_client.return_value.sandbox_task_latest.return_value = task
    response = action.run({"sha256": "aa" * 32, "sandbox": task.sandbox, **extra})
    assert response is not None
    return response


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_include_raw_report_defaults_to_returning_the_whole_report(
    mock_build_client: MagicMock, action: Report
) -> None:
    task = _make_sandbox_task(config={"cape_malscore": 6.0}, report=CAPE_REPORT)
    response = _run_with_flag(mock_build_client, action, task)
    assert response["report"] == CAPE_REPORT

    explicit = _run_with_flag(mock_build_client, action, task, include_raw_report=True)
    assert explicit == response


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_include_raw_report_false_nulls_only_the_report(mock_build_client: MagicMock, action: Report) -> None:
    task = _make_sandbox_task(config={"cape_malscore": 6.0}, report=CAPE_REPORT)
    full = _run_with_flag(mock_build_client, action, task)
    slim = _run_with_flag(mock_build_client, action, task, include_raw_report=False)

    assert slim["report"] is None
    assert {k: v for k, v in slim.items() if k != "report"} == {k: v for k, v in full.items() if k != "report"}
    assert slim["behavior"] == full["behavior"]
    assert slim["behavior"]["behavior_signatures"]
    assert slim["unscored"] is False


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_include_raw_report_false_still_gives_the_malicious_verdict(
    mock_build_client: MagicMock, action: Report
) -> None:
    task = _make_sandbox_task(config={"cape_malscore": 9.0}, report=CAPE_REPORT)
    response = _run_with_flag(mock_build_client, action, task, include_raw_report=False)
    assert response["malicious"] is True
    assert response["report"] is None
    assert action._outputs == {"malicious": True}

    triage = _make_sandbox_task(sandbox="triage", config={"traige_analysis_score": 8}, report=TRIAGE_REPORT)
    response = _run_with_flag(mock_build_client, action, triage, include_raw_report=False)
    assert response["malicious"] is True


@patch("polyswarm_modules.action_polyswarm_report.build_client", new_callable=autospec_build_client)
def test_include_raw_report_false_keeps_the_unscored_flag(mock_build_client: MagicMock, action: Report) -> None:
    task = _make_sandbox_task(sandbox="cape", report=_NO_FAMILY_REPORT, config={})
    response = _run_with_flag(mock_build_client, action, task, include_raw_report=False)
    assert response["malicious"] is None
    assert response["unscored"] is True
    assert response["report"] is None
