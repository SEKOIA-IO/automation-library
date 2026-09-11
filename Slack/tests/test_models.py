from slack_modules.models import SlackAuditLogsModuleConfiguration


def test_token_is_declared_as_a_secret():
    schema = SlackAuditLogsModuleConfiguration.model_json_schema()

    assert schema["properties"]["token"]["secret"] is True
    assert "token" in schema["required"]


def test_base_url_defaults_to_the_slack_audit_api():
    configuration = SlackAuditLogsModuleConfiguration(token="xoxp-test")

    assert configuration.base_url == "https://api.slack.com/audit/v1"
