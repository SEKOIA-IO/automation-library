from pathlib import Path

MAIN = Path(__file__).resolve().parent.parent / "main.py"


def test_main_registers_the_connector_and_the_account_validator():
    source = MAIN.read_text()

    assert 'module.register(SlackAuditLogsConnector, "SlackAuditLogsConnector")' in source
    assert "module.register_account_validator(SlackAuditLogsAccountValidator)" in source
