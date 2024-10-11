import pytest

from crowdstrike_falcon.helpers import (
    VerticleID,
    compute_refresh_interval,
    get_detection_id,
    get_extended_verticle_type,
    group_edges_by_verticle_type,
)


def test_verticle_id():
    assert VerticleID.parse("pid:835449907c99453085a924a16e967be5:8322695771") == VerticleID(
        "pid", "835449907c99453085a924a16e967be5", "8322695771"
    )
    with pytest.raises(ValueError):
        VerticleID.parse("invalid_verticle_id")


def test_get_extended_verticle_type():
    assert get_extended_verticle_type("pid:835449907c99453085a924a16e967be5:8322695771") == "processes"
    assert get_extended_verticle_type("dns:a436b1994d7441c46651e3f61d446c43:google.com") == "domains"
    assert (
        get_extended_verticle_type(
            "uid:0123456789abcdef0123456789abcdef:S-1-12-4-455030394-1452481303-1888219964-9019097"
        )
        == "users"
    )
    assert get_extended_verticle_type("invalid:835449907c99453085a924a16e967be5:google.fr") is None
    assert get_extended_verticle_type(None) is None


def test_group_edges_by_verticle_type():
    edges = [
        {"id": "pid:835449907c99453085a924a16e967be5:8322695771"},
        {"id": "dns:a436b1994d7441c46651e3f61d446c43:google.com"},
        {
            "id": "mod:0123456789abcdef0123456789abcdef:48985b22a895154cc44f9eb77489cfdf54fa54506e8ecaef492fe30f40d27e90"  # noqa: E501
        },
        {"id": "pid:0123456789abcdef0123456789abcdef:9981722433579"},
        {"id": "pid:0123456789abcdef0123456789abcdef:9981755598128"},
        {"id": "uid:0123456789abcdef0123456789abcdef:S-1-12-4-455030394-1452481303-1888219964-9019097"},
        {"id": "pid:0123456789abcdef0123456789abcdef:1111111111"},
        {"id": "uid:0123456789abcdef0123456789abcdef:222222222222"},
        {"id": "ctg:835449907c99453085a924a16e967be5:4444444"},
    ]
    assert list(group_edges_by_verticle_type(edges, 2)) == [
        (
            "processes",
            [
                {"id": "pid:835449907c99453085a924a16e967be5:8322695771"},
                {"id": "pid:0123456789abcdef0123456789abcdef:9981722433579"},
            ],
        ),
        (
            "processes",
            [
                {"id": "pid:0123456789abcdef0123456789abcdef:9981755598128"},
                {"id": "pid:0123456789abcdef0123456789abcdef:1111111111"},
            ],
        ),
        (
            "users",
            [
                {"id": "uid:0123456789abcdef0123456789abcdef:S-1-12-4-455030394-1452481303-1888219964-9019097"},
                {"id": "uid:0123456789abcdef0123456789abcdef:222222222222"},
            ],
        ),
        ("domains", [{"id": "dns:a436b1994d7441c46651e3f61d446c43:google.com"}]),
        (
            "modules",
            [
                {
                    "id": "mod:0123456789abcdef0123456789abcdef:48985b22a895154cc44f9eb77489cfdf54fa54506e8ecaef492fe30f40d27e90"  # noqa: E501
                }
            ],
        ),
        ("control-graphs", [{"id": "ctg:835449907c99453085a924a16e967be5:4444444"}]),
    ]


def test_get_detection_id():
    audit = {
        "metadata": {
            "customerIDString": "11111111111111111111111111111111",
            "offset": 1411585,
            "eventType": "UserActivityAuditEvent",
            "eventCreationTime": 1664892955000,
            "version": "1.0",
        },
        "event": {"OperationName": "detection_update", "ServiceName": "detections"},
    }
    assert get_detection_id(audit) is None
    detection_id = "ldt:445f78e41b0d4a2d962fb5991537081a:4297183213"
    detection = {
        "metadata": {
            "customerIDString": "11111111111111111111111111111111",
            "offset": 1411586,
            "eventType": "DetectionSummaryEvent",
            "eventCreationTime": 1664892972000,
            "version": "1.0",
        },
        "event": {
            "DetectName": "Authentication Bypass",
            "SensorId": "445f78e41b0d4a2d962fb5991537081a",
            "DetectId": detection_id,
        },
    }
    assert get_detection_id(detection) == detection_id


@pytest.mark.parametrize("interval,expected_result", [(1800, 1500), (60, 50), (30, 30), (3600, 3300)])
def test_compute_refresh_interval(interval, expected_result):
    assert compute_refresh_interval(interval) == expected_result
