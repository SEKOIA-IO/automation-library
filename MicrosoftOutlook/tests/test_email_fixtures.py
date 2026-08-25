from email import policy
from email.parser import Parser
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mail_samples"


def parse_eml(path: Path):
    return Parser(policy=policy.default).parsestr(path.read_text(encoding="utf-8"))


def test_incoming_anonymized_eml_headers_are_parseable():
    message = parse_eml(FIXTURES_DIR / "incoming_sample_anonymized.eml")

    assert message["Subject"] == "E2E-OUTLOOK-ANON-01"
    assert message["Message-ID"] == "<incoming-sample-0001@example.test>"
    assert message["X-MS-Exchange-Organization-Network-Message-Id"] == "11111111-2222-3333-4444-555555555555"


def test_forwarded_anonymized_eml_headers_are_parseable():
    message = parse_eml(FIXTURES_DIR / "forwarded_sample_anonymized.eml")

    assert message["Subject"] == "FW: MicrosoftOutlook e2e update"
    assert message["Message-ID"] == "<forwarded-sample-0001@example.test>"
    assert message["X-MS-Exchange-Organization-Network-Message-Id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_anonymized_eml_fixtures_do_not_contain_real_domains():
    for path in FIXTURES_DIR.glob("*.eml"):
        content = path.read_text(encoding="utf-8").lower()
        assert "sekoia.io" not in content
        assert "onmicrosoft.com" not in content
