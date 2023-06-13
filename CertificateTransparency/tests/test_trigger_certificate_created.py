import re
from unittest.mock import Mock, patch

import pytest

from certificatetransparency.triggers.certificate_updated import CertificateUpdatedTrigger


def create_trigger(configuration: dict | None = None, compile_re: bool = True) -> CertificateUpdatedTrigger:
    trigger = CertificateUpdatedTrigger()
    trigger.configuration = configuration if configuration else {}
    trigger.log = Mock()
    if compile_re:
        trigger._re_split = re.compile(r"\W+")
    return trigger


@pytest.mark.parametrize(
    "domain,result_expected",
    [
        ("sekoia.com", "sekoia"),
        ("sekoia.abc.com", "sekoia"),
        ("sekoia-admin-panel.com", "sekoia"),
        ("sekola.com", "sekoia"),
        ("sek0la", "sekoia"),
        ("sek.com", False),
        ("splunk.com", False),
    ],
)
def test_contains_keyword(domain, result_expected):
    trigger = create_trigger({"keywords": ["sekoia"], "max_distance": 2})

    result = trigger._contains_keywords(domain)

    assert result is result_expected


def test_analyse_domain_all():
    event = {
        "message_type": "certificate_update",
        "data": {"leaf_cert": {"all_domains": ["sekoia.com", "lambda"]}},
    }

    trigger = create_trigger({"keywords": ["sekoia"]})

    with patch.object(trigger, "send_event", Mock()) as mock:
        trigger.analyse_domain(event, None)

        mock.assert_called_once_with(
            event_name="sekoia.com",
            event={
                "matched_keyword": "sekoia",
                "domain": "sekoia.com",
                "certstream_object": event["data"],
            },
        )


def test_run():
    trigger = create_trigger(configuration={"keywords": ["sekoia"], "ignoring": ["amazon"]}, compile_re=False)
    with patch("certificatetransparency.triggers.certificate_updated.certstream.listen_for_events") as certstream_mock:
        trigger.run()

        assert trigger._ignoring == ["email", "mail", "cloud", "amazon"]
        certstream_mock.assert_called_once_with(trigger.analyse_domain, url="wss://certstream.calidog.io/")


def test_run_stop_without_keywords():
    trigger = create_trigger()
    with patch("certificatetransparency.triggers.certificate_updated.certstream.listen_for_events") as certstream_mock:
        assert trigger.run() is None
        assert certstream_mock.call_count == 0
