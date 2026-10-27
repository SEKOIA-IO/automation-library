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


def find_unreleased_section(lines: List[str]) -> Optional[int]:
    """Find the line index of the ## Unreleased section."""
    for i, line in enumerate(lines):
        if line.strip() == "## Unreleased" or line.strip() == "## [Unreleased]":
            return i
    return None


def version_exists(lines: List[str], version: str, date: str) -> bool:
    """Check if a version entry already exists."""
    version_header = f"## {date} - {version}"
    for line in lines:
        if line.strip() == version_header:
            return True
    return False


def insert_new_version_entry(
    lines: List[str],
    version: str,
    date: str,
    category: str,
    message: str
) -> List[str]:
    """Insert a new version entry into the changelog."""
    unreleased_idx = find_unreleased_section(lines)
    
    if unreleased_idx is None:
        typer.echo("Error: Could not find '## Unreleased' section in changelog")
        raise typer.Exit(1)
    
    # Check if version already exists
    if version_exists(lines, version, date):
        typer.echo(f"Error: Version {version} with date {date} already exists in changelog")
        raise typer.Exit(1)
    
    # Find insertion point (after ## Unreleased and its blank line)
    insert_idx = unreleased_idx + 1
    
    # Skip blank lines after Unreleased
    while insert_idx < len(lines) and lines[insert_idx].strip() == "":
        insert_idx += 1
    
    # Create new version entry
    new_entry = [
        f"## {date} - {version}\n",
        "\n",
        f"### {category}\n",
        "\n",
        f"- {message}\n\n",
    ]
    
    # Insert the new entry
    result = lines[:insert_idx] + new_entry + lines[insert_idx:]
    
    return result


def add_to_existing_version(
    lines: List[str],
    version: str,
    date: str,
    category: str,
    message: str
) -> List[str]:
    """Add an entry to an existing version section."""
    version_header = f"## {date} - {version}"
    version_idx = None
    
    # Find the version header
    for i, line in enumerate(lines):
        if line.strip() == version_header:
            version_idx = i
            break
    
    if version_idx is None:
        typer.echo(f"Error: Version {version} with date {date} not found")
        raise typer.Exit(1)
    
    # Look for the category section within this version
    category_header = f"### {category}"
    category_idx = None
    next_version_idx = len(lines)
    
    # Find the next version header to limit our search
    for i in range(version_idx + 1, len(lines)):
        if lines[i].startswith("## ") and not lines[i].startswith("###"):
            next_version_idx = i
            break
    
    # Look for category within this version
    for i in range(version_idx + 1, next_version_idx):
        if lines[i].strip() == category_header:
            category_idx = i
            break
    
    if category_idx is not None:
        # Category exists, add message to it
        # Find the last bullet point in this category
        insert_idx = category_idx + 1
        
        # Skip blank line after category header
        if insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1
        
        # Find the end of this category section
        while insert_idx < next_version_idx:
            if lines[insert_idx].startswith("### "):
                # Found next category
                break
            if lines[insert_idx].startswith("- "):
                insert_idx += 1
            else:
                break
        
        # Insert new message
        result = lines[:insert_idx] + [f"- {message}\n"] + lines[insert_idx:]
    else:
        # Category doesn't exist, create it
        # Find where to insert the new category (after version header)
        insert_idx = version_idx + 1
        
        # Skip blank lines
        while insert_idx < next_version_idx and lines[insert_idx].strip() == "":
            insert_idx += 1
        
        # Insert new category with message
        new_category = [
            f"### {category}\n",
            "\n",
            f"- {message}\n\n",
        ]
        result = lines[:insert_idx] + new_category + lines[insert_idx:]
    
    return result


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
    version_header = f"## {date_str} - {version}"
    if version_exists(lines, version, date_str):
        # Add to existing version
        updated_lines = add_to_existing_version(
            lines, version, date_str, category, message
        )
        action = f"Added entry to existing version {version}"
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
        typer.echo(f"Version: {date_str} - {version}")
        typer.echo(f"Category: {category}")
        typer.echo(f"Message: {message}")
        typer.echo("\n=== Preview of new entry ===")
        
        # Find and display the relevant section
        for i, line in enumerate(updated_lines):
            if version_header in line:
                # Show context around the change
                start = max(0, i - 2)
                end = min(len(updated_lines), i + 15)
                typer.echo("".join(updated_lines[start:end]))
                break
    else:
        write_changelog(changelog_path, updated_lines)
        typer.echo(f"✓ {action}")
        typer.echo(f"  Category: {category}")
        typer.echo(f"  Message: {message}")
        typer.echo(f"  File: {changelog_path}")


if __name__ == "__main__":
    app()
