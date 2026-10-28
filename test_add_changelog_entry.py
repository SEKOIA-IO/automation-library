import pytest
import typer

from add_changelog_entry import add_to_existing_version, find_version, insert_new_version_entry


def lines(text):
    return text.splitlines(keepends=True)


def test_find_version_heading_formats():
    for heading in ("## 2026-01-01 - 1.2.3", "## 1.2.3 - 2026-01-01", "## [1.2.3] - 2026-01-01"):
        assert find_version(lines(f"# Changelog\n\n{heading}\n"), "1.2.3") == 2
    assert find_version(lines("## 2026-01-01 - 1.2.4\n"), "1.2.3") is None
    assert find_version(lines("## Unreleased\n"), "1.2.3") is None


def test_insert_creates_missing_unreleased():
    text = "# Changelog\n\nintro\n\n## 2026-01-01 - 1.0.0\n\n### Added\n\n- a\n"
    result = "".join(insert_new_version_entry(lines(text), "1.0.1", "2026-02-01", "Changed", "dep"))
    assert result == (
        "# Changelog\n\nintro\n\n## Unreleased\n\n## 2026-02-01 - 1.0.1\n\n### Changed\n\n- dep\n\n"
        "## 2026-01-01 - 1.0.0\n\n### Added\n\n- a\n"
    )


def test_insert_keeps_unreleased_content_above_the_release():
    text = "## Unreleased\n\n### Added\n\n- pending\n\n## 2026-01-01 - 1.0.0\n\n### Added\n\n- a\n"
    result = "".join(insert_new_version_entry(lines(text), "1.0.1", "2026-02-01", "Changed", "dep"))
    assert result.startswith("## Unreleased\n\n### Added\n\n- pending\n\n## 2026-02-01 - 1.0.1\n\n### Changed")
    assert "## 2026-01-01 - 1.0.0" in result


def test_insert_refuses_existing_version():
    with pytest.raises(typer.Exit):
        insert_new_version_entry(lines("## [1.0.0] - 2026-01-01\n"), "1.0.0", "2026-02-01", "Fixed", "x")


def test_append_keeps_multiline_bullets_together():
    text = "## 2026-01-01 - 1.0.0\n\n### Fixed\n\n- first\n  wrapped\n  - nested\n\n### Added\n\n- a\n"
    result = "".join(add_to_existing_version(lines(text), "1.0.0", "Fixed", "new"))
    assert result == (
        "## 2026-01-01 - 1.0.0\n\n### Fixed\n\n- first\n  wrapped\n  - nested\n- new\n\n### Added\n\n- a\n"
    )


def test_append_to_bracketed_heading():
    text = "## [1.0.0] - 2026-01-01\n\n### Fixed\n\n- first\n"
    result = "".join(add_to_existing_version(lines(text), "1.0.0", "Fixed", "new"))
    assert result.endswith("- first\n- new\n")


def test_new_category_follows_conventional_order():
    text = "## 2026-01-01 - 1.0.0\n\n### Added\n\n- a\n\n### Security\n\n- s\n\n## 2025-01-01 - 0.9.0\n"
    result = "".join(add_to_existing_version(lines(text), "1.0.0", "Fixed", "f"))
    assert result.index("### Added") < result.index("### Fixed") < result.index("### Security")
    last = "".join(add_to_existing_version(lines(text), "1.0.0", "Changed", "c"))
    assert last.index("### Added") < last.index("### Changed")
    tail = "".join(add_to_existing_version(lines("## 1.0.0 - 2026-01-01\n\n### Added\n\n- a\n"), "1.0.0", "Fixed", "f"))
    assert tail == "## 1.0.0 - 2026-01-01\n\n### Added\n\n- a\n\n### Fixed\n\n- f\n"


@pytest.mark.parametrize("heading", ["## 2026-01-01 - 1.0.0", "## 1.0.0 - 2026-01-01", "## [1.0.0] - 2026-01-01"])
def test_existing_version_is_found_whatever_the_date(heading):
    text = f"{heading}\n\n### Fixed\n\n- first\n"
    assert find_version(lines(text), "1.0.0") == 0
    result = "".join(add_to_existing_version(lines(text), "1.0.0", "Fixed", "new"))
    assert result == f"{heading}\n\n### Fixed\n\n- first\n- new\n"
    assert result.count("1.0.0") == 1


def test_insert_refuses_existing_version_under_another_date():
    with pytest.raises(typer.Exit):
        insert_new_version_entry(lines("## 2026-10-27 - 1.0.0\n"), "1.0.0", "2026-10-28", "Fixed", "x")
