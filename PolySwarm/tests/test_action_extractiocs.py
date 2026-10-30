import os
from pathlib import Path
from unittest.mock import patch

import pytest

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_extractiocs import (
    IANA_TLDS,
    MAX_INPUT_BYTES,
    TLD_FILE,
    ExtractIocs,
    load_tlds,
)


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


def test_text_over_the_size_limit_is_refused(action: ExtractIocs) -> None:
    response = action.run({"text": "x" * (MAX_INPUT_BYTES + 1)})

    assert response is None
    assert "limit" in action.error_message


def test_an_oversized_file_is_refused_without_being_read(action: ExtractIocs, data_storage: str) -> None:
    path = Path(data_storage) / "capture.txt"
    path.write_bytes(b"x" * (MAX_INPUT_BYTES + 1))

    with patch.object(Path, "read_bytes", side_effect=AssertionError("read before the size check"), autospec=True):
        response = action.run({"file": path.name})

    assert response is None
    assert "limit" in action.error_message


# --- what counts as public, and how the run time grows ---


def test_shared_address_space_is_reported_as_reserved(
    action: ExtractIocs,
) -> None:
    response = action.run({"text": "Carrier side 100.64.1.1 and 100.127.255.254, public 8.8.8.8"})

    assert response["ipv4"] == ["8.8.8.8"]
    assert response["reserved_ip"] == ["100.64.1.1", "100.127.255.254"]


@pytest.mark.parametrize("address", ["8.8.8.8", "45.33.32.156", "2606:4700:4700::1111"])
def test_every_reported_public_address_is_accepted_by_the_ip_validator(action: ExtractIocs, address: str) -> None:
    from polyswarm_modules.validators import invalid_ip_reason

    response = action.run({"text": f"seen {address}"})

    assert invalid_ip_reason((response["ipv4"] + response["ipv6"])[0]) is None


def test_dedup_keeps_first_seen_order_across_many_repeats(action: ExtractIocs) -> None:
    text = " ".join(["b.example.com", "a.example.com"] * 500 + ["c.example.com"])

    response = action.run({"text": text})

    assert response["domain"] == ["b.example.com", "a.example.com", "c.example.com"]


def test_the_longest_overlapping_match_still_wins(action: ExtractIocs) -> None:
    response = action.run(
        {"text": "see https://evil.example.com/a and evil.example.com and mail bob@evil.example.com"}
    )

    assert response["url"] == ["https://evil.example.com/a"]
    assert response["domain"] == ["evil.example.com"]
    assert response["email"] == ["bob@evil.example.com"]


def test_a_long_run_of_closing_brackets_does_not_slow_the_trim(action: ExtractIocs) -> None:
    import time

    started = time.perf_counter()
    response = action.run({"text": "http://a.example.com/" + ")" * 100_000})

    assert time.perf_counter() - started < 5
    assert response["url"] == ["http://a.example.com/"]


def test_run_time_does_not_grow_with_the_square_of_the_match_count(action: ExtractIocs) -> None:
    """Over a megabyte of dense indicators took many seconds when each candidate was compared with every kept match."""
    import time

    lines = [
        f"host{i}.example.com https://evil{i}.example.net/p {i % 250}.{i % 200}.1.1 user{i}@mail.example.org\n"
        for i in range(15_000)
    ]
    text = "".join(lines)
    assert len(text) > 1_000_000

    started = time.perf_counter()
    response = action.run({"text": text})

    assert time.perf_counter() - started < 15
    assert len(response["url"]) == 15_000


def test_a_run_of_percent_signs_does_not_blow_up_the_email_pattern(action: ExtractIocs) -> None:
    """A percent sign is valid in a local part.

    Allowing one behind the match made every position after one rescan to the
    end of the input.
    """
    import time

    text = "a%" * 40_000
    assert len(text) == 80_000

    started = time.perf_counter()
    response = action.run({"text": text})

    assert time.perf_counter() - started < 2
    assert response["email"] == []


# --- the vendored IANA top level domain list ---


@pytest.mark.parametrize("tld", ["ai", "ly", "to", "gg", "vn"])
def test_domain_on_a_tld_the_old_hand_list_missed_is_extracted(action: ExtractIocs, tld: str) -> None:
    response = action.run({"text": f"C2 at beacon-host.{tld} was seen"})

    assert response["domain"] == [f"beacon-host.{tld}"]


@pytest.mark.parametrize("tld", ["ai", "ly", "to", "gg", "vn"])
def test_url_and_email_on_a_new_tld_are_extracted(action: ExtractIocs, tld: str) -> None:
    response = action.run({"text": f"see https://drop.example.{tld}/a and mail ops@example.{tld}"})

    assert response["url"] == [f"https://drop.example.{tld}/a"]
    assert response["email"] == [f"ops@example.{tld}"]


@pytest.mark.parametrize(
    "name",
    [
        "report.doc",
        "report.docx",
        "invoice.pdf",
        "sheet.xlsx",
        "notes.txt",
        "README.md",
        "build.log",
        "run.pl",
        "lib.so",
    ],
)
def test_filename_with_a_document_extension_is_not_a_domain(action: ExtractIocs, name: str) -> None:
    response = action.run({"text": f"The attachment {name} was opened"})

    assert response["domain"] == []
    assert response["total_count"] == 0


@pytest.mark.parametrize("name", ["payload.zip", "clip.mov", "script.sh", "tool.py"])
def test_bare_name_on_a_tld_that_is_also_a_file_extension_is_a_file(action: ExtractIocs, name: str) -> None:
    # zip, mov, sh and py are real top level domains and also real file
    # extensions. A bare name is read as a file, as the old list did.
    assert name.rsplit(".", 1)[1] in IANA_TLDS

    response = action.run({"text": f"Dropped {name} on disk"})

    assert response["domain"] == []
    assert response["skipped_filenames"] == [name]


@pytest.mark.parametrize("name", ["payload.zip", "clip.mov"])
def test_url_and_email_on_a_zip_or_mov_host_are_still_extracted(action: ExtractIocs, name: str) -> None:
    response = action.run({"text": f"fetch http://{name}/x and write to ops@{name}"})

    assert response["url"] == [f"http://{name}/x"]
    assert response["email"] == [f"ops@{name}"]


def test_every_file_extension_collision_is_deliberate() -> None:
    from polyswarm_modules.action_polyswarm_extractiocs import FILE_EXTENSIONS

    assert {"zip", "mov", "sh", "py", "md"} <= set(FILE_EXTENSIONS) & IANA_TLDS


def test_vendored_list_loads_lower_case_and_is_not_trivial() -> None:
    assert TLD_FILE.is_absolute()
    assert len(IANA_TLDS) > 1000
    assert {"com", "ai", "ly", "to", "gg", "vn"} <= IANA_TLDS
    assert all(entry == entry.lower() for entry in IANA_TLDS)
    assert load_tlds() == IANA_TLDS


def test_loader_raises_when_the_file_is_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="could not be read"):
        load_tlds(tmp_path / "absent.txt")


def test_loader_raises_when_the_file_is_empty(tmp_path: Path) -> None:
    empty = tmp_path / "tlds.txt"
    empty.write_text("", encoding="ascii")

    with pytest.raises(RuntimeError, match="truncated"):
        load_tlds(empty)


def test_loader_raises_when_the_file_holds_only_comments(tmp_path: Path) -> None:
    comments = tmp_path / "tlds.txt"
    comments.write_text("# Version 1\n\n", encoding="ascii")

    with pytest.raises(RuntimeError, match="truncated"):
        load_tlds(comments)


def test_loader_raises_when_the_list_is_cut_short(tmp_path: Path) -> None:
    short = tmp_path / "tlds.txt"
    short.write_text("com\nnet\norg\n", encoding="ascii")

    with pytest.raises(RuntimeError, match="truncated"):
        load_tlds(short)


def test_loader_raises_on_a_malformed_entry(tmp_path: Path) -> None:
    bad = tmp_path / "tlds.txt"
    bad.write_text("<html>Not Found</html>\n", encoding="ascii")

    with pytest.raises(RuntimeError, match="invalid entry"):
        load_tlds(bad)


def test_loader_resolves_the_default_path_from_the_module_not_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert load_tlds() == IANA_TLDS


@pytest.mark.parametrize("name", ["evil.zip", "evil.mov", "evil.sh", "evil.py", "evil.md"])
def test_bare_name_on_a_collision_label_is_listed_as_skipped_not_as_a_domain(action: ExtractIocs, name: str) -> None:
    response = action.run({"text": f"Seen: {name}, and again {name.upper()}"})

    assert response["skipped_filenames"] == [name]
    assert response["domain"] == []


def test_skipped_filenames_do_not_count_toward_total_count(action: ExtractIocs) -> None:
    response = action.run({"text": "evil.zip clip.mov beacon-host.ai 45.33.32.156"})

    assert response["skipped_filenames"] == ["evil.zip", "clip.mov"]
    assert response["domain"] == ["beacon-host.ai"]
    assert response["total_count"] == 2


@pytest.mark.parametrize("name", ["evil.zip", "evil.mov", "evil.sh", "evil.py", "evil.md"])
def test_url_or_email_on_a_collision_host_is_not_also_skipped(action: ExtractIocs, name: str) -> None:
    response = action.run({"text": f"fetch http://{name}/x and write to ops@{name}"})

    assert response["url"] == [f"http://{name}/x"]
    assert response["email"] == [f"ops@{name}"]
    assert response["skipped_filenames"] == []
    assert response["domain"] == []


def test_ordinary_document_name_is_neither_domain_nor_skipped(action: ExtractIocs) -> None:
    response = action.run({"text": "Open report.docx and notes.txt"})

    assert response["domain"] == []
    assert response["skipped_filenames"] == []
    assert response["total_count"] == 0
