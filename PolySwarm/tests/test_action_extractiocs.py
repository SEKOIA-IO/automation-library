import os
from pathlib import Path

import pytest

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_extractiocs import MAX_INPUT_BYTES, ExtractIocs


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> ExtractIocs:
    return ExtractIocs(module=module, data_path=data_storage)


def _write_data_file(data_storage: str, name: str, content: str) -> str:
    """Write a file where Sekoia puts it, named the way a playbook refers to it."""
    path = Path(data_storage) / name
    path.write_text(content, encoding="utf-8")
    return path.name


# --- one indicator type at a time ---


def test_extracts_ipv4(action: ExtractIocs) -> None:
    response = action.run({"text": "Beacon to 45.33.32.156 every minute"})

    assert response["ipv4"] == ["45.33.32.156"]
    assert response["total_count"] == 1


def test_extracts_ipv6(action: ExtractIocs) -> None:
    response = action.run({"text": "Resolver 2001:4860:4860::8888 answered"})

    assert response["ipv6"] == ["2001:4860:4860::8888"]


def test_extracts_domain(action: ExtractIocs) -> None:
    response = action.run({"text": "C2 lives at malicious-host.top today"})

    assert response["domain"] == ["malicious-host.top"]


def test_extracts_url(action: ExtractIocs) -> None:
    response = action.run({"text": "Download from https://Evil.COM/Payload.php?id=7."})

    # The scheme and host are lower cased, the path keeps its case, and the
    # sentence final period is not part of the URL.
    assert response["url"] == ["https://evil.com/Payload.php?id=7"]


def test_extracts_hashes(action: ExtractIocs) -> None:
    text = f"md5 {'AB' * 16} sha1 {'cd' * 20} sha256 {'ef' * 32}"

    response = action.run({"text": text})

    assert response["md5"] == ["ab" * 16]
    assert response["sha1"] == ["cd" * 20]
    assert response["sha256"] == ["ef" * 32]


def test_extracts_email(action: ExtractIocs) -> None:
    response = action.run({"text": "Reply to Finance.Team@Payments.icu for the invoice"})

    assert response["email"] == ["Finance.Team@payments.icu"]


# --- defanged forms analysts paste ---


def test_extracts_defanged_url(action: ExtractIocs) -> None:
    response = action.run({"text": "hxxps://phish[.]click/login and hxxp[:]//other(.)site/a"})

    assert response["url"] == ["https://phish.click/login", "http://other.site/a"]


def test_extracts_defanged_domain_and_address(action: ExtractIocs) -> None:
    response = action.run({"text": "Hosts drop-zone{.}xyz and 185[.]220[.]101[.]5"})

    assert response["domain"] == ["drop-zone.xyz"]
    assert response["ipv4"] == ["185.220.101.5"]


def test_extracts_defanged_email(action: ExtractIocs) -> None:
    response = action.run({"text": "Contact victim[at]target[.]org or backup(at)target(.)org"})

    assert response["email"] == ["victim@target.org", "backup@target.org"]


# --- deduplication, ordering and the URL tail rule ---


def test_lists_are_deduplicated_and_order_stable(action: ExtractIocs) -> None:
    response = action.run({"text": "second.xyz then first.top then second[.]xyz then first.top"})

    assert response["domain"] == ["second.xyz", "first.top"]
    assert response["total_count"] == 2


def test_domain_inside_a_url_is_not_reported_twice(action: ExtractIocs) -> None:
    response = action.run({"text": "Only as a link: https://carrier.top/path"})

    assert response["url"] == ["https://carrier.top/path"]
    assert response["domain"] == []


def test_domain_also_seen_standalone_is_reported(action: ExtractIocs) -> None:
    response = action.run({"text": "https://carrier.top/path resolves, and carrier.top is the registrable name"})

    assert response["url"] == ["https://carrier.top/path"]
    assert response["domain"] == ["carrier.top"]


def test_email_domain_is_not_reported_as_a_domain(action: ExtractIocs) -> None:
    response = action.run({"text": "Sender was payroll@lookalike.click"})

    assert response["email"] == ["payroll@lookalike.click"]
    assert response["domain"] == []


# --- noise ---


def test_reserved_addresses_are_reported_separately(action: ExtractIocs) -> None:
    response = action.run({"text": "Pivot from 10.0.0.5 to 8.8.8.8 over fe80::1"})

    assert response["ipv4"] == ["8.8.8.8"]
    assert response["ipv6"] == []
    assert response["reserved_ip"] == ["10.0.0.5", "fe80::1"]
    assert response["total_count"] == 3


def test_filenames_and_version_strings_are_not_indicators(action: ExtractIocs) -> None:
    response = action.run({"text": "Dropped setup.exe next to report.docx, build 1.2.3"})

    assert response["domain"] == []
    assert response["total_count"] == 0


def test_five_part_dotted_number_is_not_an_address(action: ExtractIocs) -> None:
    response = action.run({"text": "Sequence 1.2.3.4.5 and octet 256.1.1.1 are not addresses"})

    assert response["ipv4"] == []
    assert response["reserved_ip"] == []


def test_empty_text_returns_empty_lists(action: ExtractIocs) -> None:
    response = action.run({"text": "Nothing of interest in this sentence."})

    assert response["total_count"] == 0
    assert response["url"] == []


# --- the file input path ---


def test_extracts_from_a_file(action: ExtractIocs, data_storage: str) -> None:
    name = _write_data_file(
        data_storage,
        "report.txt",
        "Indicators: hxxps://staging[.]monster/drop, 91.219.236.19 and " + "ab" * 32,
    )

    response = action.run({"file": name})

    assert response["url"] == ["https://staging.monster/drop"]
    assert response["ipv4"] == ["91.219.236.19"]
    assert response["sha256"] == ["ab" * 32]


def test_undecodable_bytes_do_not_lose_the_rest_of_the_file(action: ExtractIocs, data_storage: str) -> None:
    path = Path(data_storage) / "mixed.bin"
    path.write_bytes(b"\xff\xfe binary noise then 91.219.236.19\n")

    response = action.run({"file": path.name})

    assert response["ipv4"] == ["91.219.236.19"]


def test_file_over_the_size_limit_is_refused(action: ExtractIocs, data_storage: str) -> None:
    path = Path(data_storage) / "capture.txt"
    path.write_bytes(b"x" * (MAX_INPUT_BYTES + 1))

    response = action.run({"file": path.name})

    assert response is None
    assert "limit" in action.error_message


# --- argument errors ---


def test_neither_text_nor_file_errors(action: ExtractIocs) -> None:
    response = action.run({})

    assert response is None
    assert "Neither" in action.error_message


def test_blank_text_counts_as_nothing_supplied(action: ExtractIocs) -> None:
    response = action.run({"text": "   "})

    assert response is None
    assert "Neither" in action.error_message


def test_both_text_and_file_error(action: ExtractIocs, data_storage: str) -> None:
    name = _write_data_file(data_storage, "report.txt", "91.219.236.19")

    response = action.run({"text": "45.33.32.156", "file": name})

    assert response is None
    assert "Both" in action.error_message


# --- the file a playbook names stays inside the run data directory ---


def test_absolute_path_is_refused(action: ExtractIocs) -> None:
    """The Sekoia run token lives at a known absolute path in the container."""
    response = action.run({"file": "/symphony/token"})

    assert response is None
    assert "relative" in action.error_message


def test_parent_traversal_is_refused(action: ExtractIocs) -> None:
    response = action.run({"file": "../../../etc/passwd"})

    assert response is None
    assert "outside" in action.error_message


def test_symlink_out_of_the_data_directory_is_refused(action: ExtractIocs, data_storage: str) -> None:
    outside = Path(data_storage).parent / "outside-secret-extractiocs"
    outside.write_text("credential 91.219.236.19", encoding="utf-8")
    link = Path(data_storage) / "innocent.txt"
    os.symlink(outside, link)

    try:
        response = action.run({"file": link.name})
    finally:
        outside.unlink()

    assert response is None
    assert "outside" in action.error_message


def test_missing_file_is_refused(action: ExtractIocs) -> None:
    response = action.run({"file": "never-delivered.txt"})

    assert response is None
    assert "not found" in action.error_message
