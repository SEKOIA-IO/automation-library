import json
import pathlib
from brevohttp_modules.models import BrevoApiData, BrevoApiLog

TEST_DIRECTORY = pathlib.Path(__file__).parent.resolve()


def test_can_deserialize_data_coming_from_brevo():
    with open(f"{TEST_DIRECTORY}/fixtures/account_activity.json", "r") as file:
        data = file.read()
        d = BrevoApiData.model_validate_json(data, strict=True)

    assert len(d.logs) == d.count

    l = d.logs[0]

    assert l.action == "auth-ip-add-new-ip"
    assert l.date == "2026-08-13T13:09:00Z"
    assert l.user_agent == "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0"
    assert l.user_email == "user@company.com"
    assert l.user_ip == "123.123.123.123"


def test_can_serialize_a_single_log_as_json():
    d = BrevoApiLog(
        action="action",
        date="date",
        user_agent="agent",
        user_email="email",
        user_ip="ip",
    )

    result = json.loads(d.model_dump_json())

    for property in ["action", "date", "user_agent", "user_email", "user_ip"]:
        assert result[property] == getattr(d, property)


def test_add_a_property_on_serialization():
    d = BrevoApiLog(
        action="action",
        date="date",
        user_agent="agent",
        user_email="email",
        user_ip="ip",
    )

    result = json.loads(d.model_dump_json())

    assert result["source"] == "brevo"
