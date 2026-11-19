import pytest

from crowdstrike_falcon.helpers import (
    VerticleID,
    compute_refresh_interval,
    get_detection_id,
    get_epp_detection_composite_id,
    get_extended_verticle_type,
    group_edges_by_verticle_type,
    is_a_supported_stix_indicator,
    stix_to_indicators,
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


def test_group_edges_by_verticle_type_skips_unusable_edges():
    edges = [
        {"source_vertex_id": "no-id"},
        {"id": "malformed-verticle-id"},
        {"id": "unknown:835449907c99453085a924a16e967be5:1"},
        {"id": "pid:835449907c99453085a924a16e967be5:8322695771"},
    ]

    assert list(group_edges_by_verticle_type(iter(edges))) == [
        ("processes", [{"id": "pid:835449907c99453085a924a16e967be5:8322695771"}])
    ]


def test_get_epp_detection_composite_id():
    composite_id = "ad5f82e879a9c5d6b5b442eb37e50551:ind:835449907c99453085a924a16e967be5:17212155109-1-2"
    assert (
        get_epp_detection_composite_id(
            {"metadata": {"eventType": "EppDetectionSummaryEvent"}, "event": {"CompositeId": composite_id}}
        )
        == composite_id
    )
    assert get_epp_detection_composite_id({"metadata": {"eventType": "DetectionSummaryEvent"}}) is None
    assert get_epp_detection_composite_id({}) is None


@pytest.mark.parametrize(
    "stix_object,expected",
    [
        ({"type": "indicator", "pattern_type": "stix"}, True),
        ({"type": "indicator"}, True),
        ({"type": "indicator", "pattern_type": "sigma"}, False),
        ({"type": "malware"}, False),
    ],
)
def test_is_a_supported_stix_indicator(stix_object, expected):
    assert is_a_supported_stix_indicator(stix_object) is expected


SUPPORTED_TYPES_MAP = {
    "ipv4-addr": {"value": "ipv4"},
    "file": {"hashes.MD5": "md5"},
}


def test_stix_to_indicators():
    stix_object = {
        "type": "indicator",
        "pattern_type": "stix",
        "pattern": "[ipv4-addr:value = '1.2.3.4'] OR [file:hashes.MD5 = 'd41d8cd98f00b204e9800998ecf8427e']",
    }

    assert sorted(stix_to_indicators(stix_object, SUPPORTED_TYPES_MAP), key=lambda ioc: ioc["type"]) == [
        {"type": "ipv4", "value": "1.2.3.4"},
        {"type": "md5", "value": "d41d8cd98f00b204e9800998ecf8427e"},
    ]


@pytest.mark.parametrize(
    "pattern",
    [
        # unsupported observable type
        "[domain-name:value = 'example.com']",
        # unsupported path for a supported observable type
        "[file:name = 'evil.exe']",
        # unsupported operator
        "[ipv4-addr:value != '1.2.3.4']",
        # wildcard in the path
        "[file:hashes[*] = 'd41d8cd98f00b204e9800998ecf8427e']",
    ],
)
def test_stix_to_indicators_ignores_unsupported_comparisons(pattern):
    stix_object = {"type": "indicator", "pattern_type": "stix", "pattern": pattern}

    assert stix_to_indicators(stix_object, SUPPORTED_TYPES_MAP) == []


def test_stix_to_indicators_ignores_non_stix_indicators():
    stix_object = {"type": "indicator", "pattern_type": "yara", "pattern": "rule test { condition: true }"}

    assert stix_to_indicators(stix_object, SUPPORTED_TYPES_MAP) == []
