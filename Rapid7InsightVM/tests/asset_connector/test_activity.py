import pytest

from rapid7_insightvm.asset_connector import activity
from tests.asset_connector.builders import OTHER_VULN_ID, THIRD_VULN_ID, VULN_ID, asset, finding, make_finding


def delta(new=(), same=(), remediated=()) -> activity.VulnerabilityDelta:
    def parse(items):
        return [finding(**item) for item in items]

    return activity.VulnerabilityDelta(new=parse(new), same=parse(same), remediated=parse(remediated))


@pytest.mark.parametrize(
    "status, expected",
    [
        ("VULNERABLE_EXPL", True),
        ("VULNERABLE_VERS", True),
        ("vulnerable_potential", True),
        ("EXCEPTION_VULN_EXPL", False),
        ("NOT_VULNERABLE", False),
        (None, False),
    ],
)
def test_is_vulnerable(status, expected):
    assert activity.is_vulnerable(status) is expected


@pytest.mark.parametrize(
    "first_run, buckets, expected",
    [
        # first run: open in same -> Create, nothing else
        (True, {"same": [{}]}, activity.CREATE),
        (True, {"same": [{"status": "EXCEPTION_VULN_EXPL"}]}, None),
        (True, {"remediated": [{}]}, None),
        # open in new -> Create, reintroduced -> Update
        (False, {"new": [{}]}, activity.CREATE),
        (False, {"new": [{}, {"reintroduced": "2026-10-01T00:00:00Z"}]}, activity.UPDATE),
        # open in remediated, not open in new -> Close
        (False, {"remediated": [{}]}, activity.CLOSE),
        (False, {"new": [{"status": "EXCEPTION_VULN_VERS"}], "remediated": [{}]}, activity.CLOSE),
        # moved to another port with the same status -> no change
        (False, {"new": [{"port": 443}], "remediated": [{"port": 22}]}, None),
        # fixed on one port, still open on another -> no Close
        (False, {"same": [{"port": 8443}], "remediated": [{"port": 443}]}, None),
        # status change of an open vulnerability -> Update
        (
            False,
            {"new": [{"status": "VULNERABLE_EXPL"}], "remediated": [{"status": "VULNERABLE_VERS"}]},
            activity.UPDATE,
        ),
        (False, {"same": [{"port": 22}], "new": [{"port": 443, "status": "VULNERABLE_VERS"}]}, activity.UPDATE),
        # first run: open in new is also a Create
        (True, {"new": [{}]}, activity.CREATE),
        # non-open statuses are not emitted
        (False, {"remediated": [{"status": "EXCEPTION_VULN_EXPL"}]}, None),
        (False, {"new": [{"status": "NOT_VULNERABLE"}]}, None),
        (False, {"new": [{"status": "EXCEPTION_VULN_POTL"}]}, None),
        # same outside the first run -> nothing
        (False, {"same": [{}]}, None),
    ],
)
def test_detect_change(first_run, buckets, expected):
    decision = activity.detect_change(delta(**buckets), first_run)
    if expected is None:
        assert decision is None
    else:
        assert decision[0] == expected
        assert all(activity.is_vulnerable(item.status) for item in decision[1])


def test_detect_change_close_uses_the_remediated_findings():
    decided, findings = activity.detect_change(
        delta(remediated=[{"port": 22}, {"port": 80, "status": "NOT_VULNERABLE"}]), False
    )
    assert decided == activity.CLOSE
    assert [item.port for item in findings] == [22]


def test_split_by_vulnerability_merges_duplicates():
    groups = activity.split_by_vulnerability(
        asset(
            new=[make_finding(port=22), make_finding(OTHER_VULN_ID), make_finding(port=2222)],
            same=[make_finding(port=8022)],
            remediated=[make_finding(THIRD_VULN_ID)],
        )
    )

    assert list(groups) == [VULN_ID, OTHER_VULN_ID, THIRD_VULN_ID]
    assert [item.port for item in groups[VULN_ID].new] == [22, 2222]
    assert [item.port for item in groups[VULN_ID].same] == [8022]
    assert len(groups[THIRD_VULN_ID].remediated) == 1
