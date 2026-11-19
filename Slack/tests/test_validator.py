import requests_mock

from slack_modules import SlackAuditLogsModule
from slack_modules.client import AuditLogsClient
from slack_modules.validator import SlackAuditLogsAccountValidator

BASE_URL = "https://api.slack.test/audit/v1"


def make_validator(tmp_path):
    module = SlackAuditLogsModule()
    module.configuration = {"token": "xoxp-test", "base_url": BASE_URL}
    return SlackAuditLogsAccountValidator(module=module, data_path=tmp_path)


def test_validate_returns_true_when_the_api_answers(tmp_path, monkeypatch):
    validator = make_validator(tmp_path)
    monkeypatch.setattr(validator, "error", lambda message: None)

    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", json={"entries": [], "response_metadata": {"next_cursor": ""}})

        assert validator.validate() is True


def test_validate_returns_false_and_reports_the_slack_error_code(tmp_path, monkeypatch):
    validator = make_validator(tmp_path)
    reported: list[str] = []
    monkeypatch.setattr(validator, "error", reported.append)

    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", status_code=401, json={"ok": False, "error": "not_authed"})

        assert validator.validate() is False

    assert "not_authed" in reported[0]
    assert "auditlogs:read" in reported[0]


def test_validate_distinguishes_a_plan_restriction_from_a_bad_token(tmp_path, monkeypatch):
    validator = make_validator(tmp_path)
    reported: list[str] = []
    monkeypatch.setattr(validator, "error", reported.append)

    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", json={"ok": False, "error": "paid_only"})

        assert validator.validate() is False

    assert "Enterprise Grid" in reported[0]
    assert "rejected the token" not in reported[0]


def test_validate_reports_a_generic_api_failure_without_blaming_the_token(tmp_path, monkeypatch):
    validator = make_validator(tmp_path)
    reported: list[str] = []
    monkeypatch.setattr(validator, "error", reported.append)

    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", status_code=500, text="boom")

        assert validator.validate() is False

    assert "may still be valid" in reported[0]


def test_validate_survives_a_client_that_cannot_even_be_built(tmp_path, monkeypatch):
    validator = make_validator(tmp_path)
    reported: list[str] = []
    monkeypatch.setattr(validator, "error", reported.append)

    def refuse_to_build(*args, **kwargs):
        raise RuntimeError("adapter mount failed")

    monkeypatch.setattr("slack_modules.validator.AuditLogsClient", refuse_to_build)

    assert validator.validate() is False
    assert "Unexpected failure" in reported[0]


def test_validate_reports_an_unexpected_failure_instead_of_raising(tmp_path, monkeypatch):
    validator = make_validator(tmp_path)
    reported: list[str] = []
    monkeypatch.setattr(validator, "error", reported.append)

    def explode(self, oldest, latest, limit):
        raise RuntimeError("boom")
        yield

    monkeypatch.setattr(AuditLogsClient, "iter_pages", explode)

    assert validator.validate() is False
    assert "Unexpected failure" in reported[0]
