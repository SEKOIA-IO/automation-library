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
        # C3: an unknown status starting with VULNERABLE is open
        ("VULNERABLE_NEW_KIND", True),
    ],
)
def test_is_vulnerable(status, expected):
    assert activity.is_vulnerable(status) is expected


def test_unknown_open_status():
    assert activity.is_unknown_open_status("vulnerable_new_kind") is True
    assert activity.is_unknown_open_status("VULNERABLE_EXPL") is False
    assert activity.is_unknown_open_status("SKIPPED_DOS") is False


@pytest.mark.parametrize(
    "statuses, expected",
    [
        ([], None),
        (["VULNERABLE_EXPL"], activity.State.OPEN),
        # open if any instance is open
        (["VULNERABLE_EXPL", "SKIPPED_DOS"], activity.State.OPEN),
        (["UNKNOWN", "VULNERABLE_NEW_KIND"], activity.State.OPEN),
        # closed only if every instance is closing
        (["NOT_VULNERABLE"], activity.State.CLOSED),
        (["EXCEPTION_VULN_EXPL", "SUPERSEDED", "NOT_VULN_DONT_STORE", "OVERRIDDEN_VULN_VERS"], activity.State.CLOSED),
        # otherwise inconclusive (check skipped or failed, or unrecognised)
        (["NOT_VULNERABLE", "SKIPPED_DOS"], activity.State.INCONCLUSIVE),
        (["UNEXPECTED_ERR"], activity.State.INCONCLUSIVE),
        (["SKIPPED_VERS"], activity.State.INCONCLUSIVE),
        (["SKIPPED_DISABLED"], activity.State.INCONCLUSIVE),
        (["UNKNOWN"], activity.State.INCONCLUSIVE),
        (["SOMETHING_NEW"], activity.State.INCONCLUSIVE),
        ([None], activity.State.INCONCLUSIVE),
    ],
)
def test_state_of(statuses, expected):
    assert activity.state_of([finding(status=status) for status in statuses]) is expected


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
        # moved to another port with the same status -> Update (the affected ports changed)
        (False, {"new": [{"port": 443}], "remediated": [{"port": 22}]}, activity.UPDATE),
        # fixed on one port, still open on another -> no Close, Update
        (False, {"same": [{"port": 8443}], "remediated": [{"port": 443}]}, activity.UPDATE),
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
        # inconclusive now: a skipped check in same is not a Close
        (False, {"same": [{"status": "SKIPPED_DOS"}], "remediated": [{}]}, None),
        # inconclusive now: a failed check in new is not a Create, nor a Close
        (False, {"new": [{"status": "UNEXPECTED_ERR"}]}, None),
        (False, {"new": [{"status": "UNEXPECTED_ERR"}], "remediated": [{}]}, None),
        (True, {"same": [{"status": "UNEXPECTED_ERR"}]}, None),
        # an exception closes
        (False, {"new": [{"status": "EXCEPTION_VULN_EXPL"}], "remediated": [{}]}, activity.CLOSE),
        # one open instance plus one skipped: still open, no Close; port 443 no longer vulnerable -> Update
        (
            False,
            {"same": [{"port": 22}, {"port": 443, "status": "SKIPPED_DOS"}], "remediated": [{"port": 443}]},
            activity.UPDATE,
        ),
        # one open instance plus one skipped, unchanged -> nothing
        (False, {"same": [{"port": 22}, {"port": 443, "status": "SKIPPED_DOS"}]}, None),
    ],
)
def test_detect_change(first_run, buckets, expected):
    decision = activity.detect_change(delta(**buckets), first_run)
    if expected is None:
        assert decision is None
    else:
        assert decision[0] == expected
        assert all(activity.is_vulnerable(item.status) for item in decision[1])


@pytest.mark.parametrize(
    "buckets, expected",
    [
        # M1: still open and unchanged -> re-emitted as Update
        ({"same": [{}]}, activity.UPDATE),
        ({"same": [{"port": 8443}], "remediated": [{"port": 443}]}, activity.UPDATE),
        # Closes, Creates and status changes as usual
        ({"remediated": [{}]}, activity.CLOSE),
        ({"new": [{}]}, activity.CREATE),
        ({"new": [{"status": "VULNERABLE_EXPL"}], "remediated": [{"status": "VULNERABLE_VERS"}]}, activity.UPDATE),
        # not open: nothing to re-emit
        ({"same": [{"status": "NOT_VULNERABLE"}]}, None),
        ({"same": [{"status": "SKIPPED_DOS"}]}, None),
    ],
)
def test_detect_change_full_resync(buckets, expected):
    decision = activity.detect_change(delta(**buckets), first_run=False, full_resync=True)
    assert (decision[0] if decision else None) == expected


def test_detect_change_close_uses_the_remediated_findings():
    decided, findings = activity.detect_change(
        delta(remediated=[{"port": 22}, {"port": 80, "status": "NOT_VULNERABLE"}]), False
    )
    assert decided == activity.CLOSE
    assert [item.port for item in findings] == [22]


@pytest.mark.parametrize(
    "buckets, expected",
    [
        # a port removed with the same status -> Update with the remaining open instances
        (
            {
                "same": [{"port": 22, "status": "VULNERABLE_VERS"}],
                "remediated": [{"port": 443, "status": "VULNERABLE_VERS"}],
            },
            [22],
        ),
        # a port added with the same status -> Update with every open instance
        (
            {"same": [{"port": 22, "status": "VULNERABLE_VERS"}], "new": [{"port": 443, "status": "VULNERABLE_VERS"}]},
            [22, 443],
        ),
        # same port, other protocol or key -> Update
        ({"new": [{"protocol": "UDP"}], "remediated": [{"protocol": "TCP"}]}, [22]),
        ({"new": [{"key": "/usr/sbin/sshd"}], "remediated": [{"key": ""}]}, [22]),
        # identical instances (protocol case and a null key ignored) -> nothing
        ({"new": [{"protocol": "tcp", "key": None}], "remediated": [{"protocol": "TCP", "key": ""}]}, None),
        ({"same": [{"port": 22}, {"port": 443}]}, None),
    ],
)
def test_detect_change_on_affected_instances(buckets, expected):
    decision = activity.detect_change(delta(**buckets), first_run=False)
    if expected is None:
        assert decision is None
    else:
        assert decision[0] == activity.UPDATE
        assert sorted(item.port for item in decision[1]) == expected


@pytest.mark.parametrize(
    "buckets, expected",
    [
        # open -> inconclusive (nothing emitted) -> closed: the held back Close
        ({"remediated": [{"status": "SKIPPED_VERS"}], "new": [{"status": "NOT_VULNERABLE"}]}, activity.CLOSE),
        ({"remediated": [{"status": "UNEXPECTED_ERR"}], "new": [{"status": "EXCEPTION_VULN_EXPL"}]}, activity.CLOSE),
        # closed before and after (one instance only skipped before) -> Close again, idempotent
        (
            {
                "same": [{"port": 80, "status": "NOT_VULNERABLE"}],
                "remediated": [{"port": 443, "status": "SKIPPED_DOS"}],
                "new": [{"port": 443, "status": "NOT_VULNERABLE"}],
            },
            activity.CLOSE,
        ),
        # closed before and after, nothing inconclusive -> nothing
        ({"remediated": [{"status": "EXCEPTION_VULN_EXPL"}], "new": [{"status": "NOT_VULNERABLE"}]}, None),
        ({"same": [{"status": "NOT_VULNERABLE"}]}, None),
        # inconclusive -> open: a Create as usual
        ({"remediated": [{"status": "SKIPPED_VERS"}], "new": [{}]}, activity.CREATE),
    ],
)
def test_detect_change_after_an_inconclusive_state(buckets, expected):
    decision = activity.detect_change(delta(**buckets), first_run=False)
    assert (decision[0] if decision else None) == expected


def test_detect_change_close_after_an_inconclusive_state_uses_the_before_findings():
    decided, findings = activity.detect_change(
        delta(
            remediated=[{"status": "SKIPPED_VERS", "remediation_date": "2026-10-28T10:00:00Z"}],
            new=[{"status": "NOT_VULNERABLE"}],
        ),
        first_run=False,
    )
    assert decided == activity.CLOSE
    assert [(item.status, item.remediation_date) for item in findings] == [("SKIPPED_VERS", "2026-10-28T10:00:00Z")]
    # not on a first run: only the open findings are collected
    assert (
        activity.detect_change(
            delta(remediated=[{"status": "SKIPPED_VERS"}], new=[{"status": "NOT_VULNERABLE"}]), first_run=True
        )
        is None
    )


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
