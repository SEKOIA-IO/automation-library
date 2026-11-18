#!/usr/bin/env python3
# /// script
# requires-python = ">=3.6"
# dependencies = [
#   "typer",
# ]
# ///
"""
Script to add entries to CHANGELOG.md following Keep a Changelog convention.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer


VALID_CATEGORIES = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]

app = typer.Typer(help="Add an entry to CHANGELOG.md following Keep a Changelog convention")


def validate_version(version: str) -> bool:
    """Validate semantic version format."""
    pattern = r'^\d+\.\d+\.\d+$'
    return bool(re.match(pattern, version))


def validate_date(date_str: str) -> bool:
    """Validate date format YYYY-MM-DD."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def read_changelog(filepath: Path) -> List[str]:
    """Read changelog file and return lines."""
    if not filepath.exists():
        typer.echo(f"Error: Changelog file not found: {filepath}")
        raise typer.Exit(1)
    
    with open(filepath, "r", encoding="utf-8") as f:
        return f.readlines()


# `## 2026-01-01 - 1.2.3`, `## 1.2.3 - 2026-01-01` and `## [1.2.3] - 2026-01-01`
RELEASE_HEADING = re.compile(r"^## \[?([^\]\s]+)\]? - \[?([^\]\s]+)\]?$")


def is_release_heading(line: str) -> bool:
    return line.startswith("## ")


def find_unreleased_section(lines: List[str]) -> Optional[int]:
    """Find the line index of the ## Unreleased section."""
    for i, line in enumerate(lines):
        if line.strip() == "## Unreleased" or line.strip() == "## [Unreleased]":
            return i
    return None


def find_version(lines: List[str], version: str) -> Optional[int]:
    """Find the line index of the heading of a version, whatever its date or the order of both."""
    for i, line in enumerate(lines):
        match = RELEASE_HEADING.match(line.strip())
        if match and version in match.groups():
            return i
    return None


def version_exists(lines: List[str], version: str) -> bool:
    """Check if a version entry already exists."""
    return find_version(lines, version) is not None


def section_end(lines: List[str], start: int) -> int:
    """Index of the next release heading after `start`, or the end of the file."""
    return next((i for i in range(start + 1, len(lines)) if is_release_heading(lines[i])), len(lines))


def insert_new_version_entry(
    lines: List[str],
    version: str,
    date: str,
    category: str,
    message: str
) -> List[str]:
    """Insert a new version entry into the changelog, below the content of the Unreleased section."""
    if version_exists(lines, version):
        typer.echo(f"Error: Version {version} already exists in changelog")
        raise typer.Exit(1)

    unreleased_idx = find_unreleased_section(lines)
    if unreleased_idx is None:
        # some changelogs have releases only: add the section before the first one
        unreleased_idx = next((i for i, line in enumerate(lines) if is_release_heading(line)), len(lines))
        lines = lines[:unreleased_idx] + ["## Unreleased\n", "\n"] + lines[unreleased_idx:]

    # the release goes after whatever is pending under Unreleased
    insert_idx = section_end(lines, unreleased_idx)
    new_entry = [
        f"## {date} - {version}\n",
        "\n",
        f"### {category}\n",
        "\n",
        f"- {message}\n\n",
    ]
    if insert_idx > 0 and lines[insert_idx - 1].strip():
        new_entry.insert(0, "\n")
    return lines[:insert_idx] + new_entry + lines[insert_idx:]


def add_to_existing_version(
    lines: List[str],
    version: str,
    category: str,
    message: str
) -> List[str]:
    """Add an entry to an existing version section."""
    version_idx = find_version(lines, version)
    if version_idx is None:
        typer.echo(f"Error: Version {version} not found")
        raise typer.Exit(1)

    version_end = section_end(lines, version_idx)
    headings = [i for i in range(version_idx + 1, version_end) if lines[i].startswith("### ")]

    def last_content(start: int, end: int) -> int:
        """Index after the last non-blank line of lines[start:end]."""
        while end > start and not lines[end - 1].strip():
            end -= 1
        return end

    for n, idx in enumerate(headings):
        if lines[idx].strip() == f"### {category}":
            # the category runs to the next heading: wrapped lines and nested bullets stay attached
            end = last_content(idx + 1, headings[n + 1] if n + 1 < len(headings) else version_end)
            if end == idx + 1:
                return lines[:end] + ["\n", f"- {message}\n"] + lines[end:]
            return lines[:end] + [f"- {message}\n"] + lines[end:]

    # missing category: keep the conventional order
    rank = {name: i for i, name in enumerate(VALID_CATEGORIES)}
    later = next(
        (idx for idx in headings if rank.get(lines[idx][4:].strip(), len(rank)) > rank[category]), None
    )
    if later is not None:
        return lines[:later] + [f"### {category}\n", "\n", f"- {message}\n", "\n"] + lines[later:]
    end = last_content(version_idx + 1, version_end)
    return lines[:end] + ["\n", f"### {category}\n", "\n", f"- {message}\n"] + lines[end:]


def write_changelog(filepath: Path, lines: List[str]):
    """Write the updated changelog to file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


@app.command()
def main(
    version: str = typer.Option(..., "--version", help="Version number (e.g., 1.33.8)"),
    category: str = typer.Option(..., "--category", help="Category of the change"),
    message: str = typer.Option(..., "--message", help="Description of the change"),
    changelog: str = typer.Option("CHANGELOG.md", "--changelog", help="Path to CHANGELOG.md file"),
    date: Optional[str] = typer.Option(None, "--date", help="Date in YYYY-MM-DD format (default: today)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without modifying the file"),
):
    """Add an entry to CHANGELOG.md following Keep a Changelog convention."""
    
    # Validate category
    if category not in VALID_CATEGORIES:
        typer.echo(f"Error: Invalid category: {category}")
        typer.echo(f"Valid categories: {', '.join(VALID_CATEGORIES)}")
        raise typer.Exit(1)
    
    # Validate version
    if not validate_version(version):
        typer.echo(f"Error: Invalid version format: {version}")
        typer.echo("Expected format: X.Y.Z (e.g., 1.33.8)")
        raise typer.Exit(1)
    
    # Get or validate date
    if date:
        if not validate_date(date):
            typer.echo(f"Error: Invalid date format: {date}")
            typer.echo("Expected format: YYYY-MM-DD")
            raise typer.Exit(1)
        date_str = date
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Read changelog
    changelog_path = Path(changelog)
    lines = read_changelog(changelog_path)
    
    # Check if version already exists
    if version_exists(lines, version):
        # Add to existing version, which keeps its recorded date
        updated_lines = add_to_existing_version(lines, version, category, message)
        action = f"Added entry to existing version {version}"
        if date:
            typer.echo(f"Note: {version} already exists, its recorded date is kept")
    else:
        # Create new version entry
        updated_lines = insert_new_version_entry(
            lines, version, date_str, category, message
        )
        action = f"Created new version {version}"
    
    # Preview or write
    if dry_run:
        typer.echo("=== DRY RUN MODE ===")
        typer.echo(f"{action}")
        typer.echo(f"\nChanges to be made:")
        typer.echo(f"Version: {version}")
        typer.echo(f"Category: {category}")
        typer.echo(f"Message: {message}")
        typer.echo("\n=== Preview of new entry ===")
        
        # Show context around the change
        i = find_version(updated_lines, version)
        if i is not None:
            typer.echo("".join(updated_lines[max(0, i - 2) : i + 15]))
    else:
        write_changelog(changelog_path, updated_lines)
        typer.echo(f"✓ {action}")
        typer.echo(f"  Category: {category}")
        typer.echo(f"  Message: {message}")
        typer.echo(f"  File: {changelog_path}")


if __name__ == "__main__":
    app()
