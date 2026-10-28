# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "packaging",
#     "tomlkit",
#     "typer",
# ]
# ///
"""
Bump the dependencies of a module (uv or poetry), increase the patch version
in its manifest.json and add an entry in its CHANGELOG.md.

Usage: uv run update_module_dependencies.py <ModuleDirectory>
"""

import json
import os
import re
import signal
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path
from typing import NamedTuple

import tomlkit
import typer
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from add_changelog_entry import insert_new_version_entry, read_changelog, write_changelog

app = typer.Typer()


class Dependency(NamedTuple):
    group: str | None  # None means the main dependencies
    name: str
    extras: tuple[str, ...]
    marker: str | None
    skip: str | None  # reason not to bump this dependency

    @property
    def name_with_extras(self) -> str:
        return f"{self.name}[{','.join(self.extras)}]" if self.extras else self.name


UNBOUNDED = "unbounded, left to the lock refresh"


def from_requirement(group: str | None, requirement: Requirement) -> Dependency:
    skip = None
    if requirement.url:
        skip = "direct reference"
    elif not requirement.specifier:
        skip = UNBOUNDED
    elif any(spec.operator in ("==", "===") for spec in requirement.specifier):
        skip = "pinned"
    marker = str(requirement.marker) if requirement.marker else None
    return Dependency(group, requirement.name, tuple(sorted(requirement.extras)), marker, skip)


def uv_dependencies(pyproject: dict) -> list[Dependency]:
    groups = {None: pyproject.get("project", {}).get("dependencies", [])}
    groups |= pyproject.get("dependency-groups", {})
    # non-string entries are `{include-group = ...}` references
    return [
        from_requirement(group, Requirement(req)) for group, reqs in groups.items() for req in reqs if isinstance(req, str)
    ]


def poetry_spec_skip(spec: str | dict) -> str | None:
    if isinstance(spec, dict):
        if "version" not in spec or set(spec) - {"version", "extras"}:
            return "complex specification"
        spec = spec["version"]
    if spec.strip() == "*":
        return UNBOUNDED
    if spec.startswith("==") or spec[:1].isdigit():
        return "pinned"
    return None


def poetry_dependencies(pyproject: dict) -> list[Dependency]:
    poetry = pyproject.get("tool", {}).get("poetry", {})
    groups = {None: poetry.get("dependencies", {})}
    groups |= {name: group.get("dependencies", {}) for name, group in poetry.get("group", {}).items()}
    dependencies = [
        Dependency(
            group,
            name,
            tuple(sorted(spec.get("extras", []))) if isinstance(spec, dict) else (),
            None,
            poetry_spec_skip(spec),
        )
        for group, deps in groups.items()
        for name, spec in deps.items()
        if name != "python"
    ]
    # Poetry 2 also supports PEP 621 `[project]` dependencies
    for req in pyproject.get("project", {}).get("dependencies", []):
        dependency = from_requirement(None, Requirement(req))
        if dependency.marker and not dependency.skip:
            dependency = dependency._replace(skip="has markers")
        dependencies.append(dependency)
    return dependencies


def migrate_legacy_dev_dependencies(text: str) -> str:
    """Merge `[tool.poetry.dev-dependencies]` into `[tool.poetry.group.dev.dependencies]`.

    `poetry add --group dev` would otherwise declare the package a second time,
    leaving the legacy constraint in place.
    """
    doc = tomlkit.parse(text)
    poetry = doc.get("tool", {}).get("poetry", {})
    if "dev-dependencies" not in poetry:
        return text
    resolved = tomllib.loads(text)["tool"]["poetry"]
    legacy = resolved["dev-dependencies"]
    group = resolved.get("group", {}).get("dev", {}).get("dependencies", {})
    if overlap := legacy.keys() & group.keys():
        raise ValueError(f"declared in both dev dependency tables: {', '.join(sorted(overlap))}")

    merged = tomlkit.table()
    for name, spec in {**group, **legacy}.items():
        if isinstance(spec, dict):
            inline = tomlkit.inline_table()
            inline.update(spec)
            spec = inline
        merged[name] = spec
    del poetry["dev-dependencies"]
    if "dev" in poetry.get("group", {}):
        del poetry["group"]["dev"]["dependencies"]
    groups = poetry.setdefault("group", tomlkit.table(is_super_table=True))
    groups.setdefault("dev", tomlkit.table(is_super_table=True))["dependencies"] = merged

    new_text = tomlkit.dumps(doc)
    if tomllib.loads(new_text)["tool"]["poetry"]["group"]["dev"]["dependencies"] != {**group, **legacy}:
        raise ValueError("dev dependencies changed by the migration")
    return new_text


def declaration_count(pyproject: dict, name: str) -> int:
    """Number of places declaring `name` in a pyproject.toml."""
    poetry = pyproject.get("tool", {}).get("poetry", {})
    tables = [poetry.get("dependencies", {}), poetry.get("dev-dependencies", {})]
    tables += [group.get("dependencies", {}) for group in poetry.get("group", {}).values()]
    count = sum(canonicalize_name(key) == canonicalize_name(name) for table in tables for key in table)
    requirements = list(pyproject.get("project", {}).get("dependencies", []))
    requirements += [r for reqs in pyproject.get("dependency-groups", {}).values() for r in reqs if isinstance(r, str)]
    return count + sum(canonicalize_name(Requirement(r).name) == canonicalize_name(name) for r in requirements)


def parse_uv_outdated(output: str) -> dict[str, str]:
    """Parse `uv tree --outdated --depth 1` into {canonical name: latest version}."""
    # shortcut: text parsing, switch to `--format json` once uv no longer flags it as preview
    return {
        canonicalize_name(name): latest for name, latest in re.findall(r"── (\S+) v\S+ .*\(latest: v(\S+)\)", output)
    }


def parse_poetry_outdated(output: str) -> dict[str, str]:
    """Parse `poetry show --outdated --top-level --format json` into {canonical name: latest version}."""
    return {canonicalize_name(package["name"]): package["latest_version"] for package in json.loads(output)}


def uv_requirement(dependency: Dependency, latest: str) -> str:
    marker = f"; {dependency.marker}" if dependency.marker else ""
    return f"{dependency.name_with_extras}>={latest},<{Version(latest).major + 1}{marker}"


def bump_manifest_version(text: str) -> tuple[str, str]:
    """Increase the patch version of manifest.json content, keeping its formatting."""
    old = json.loads(text)["version"]
    current = Version(old)
    new = f"{current.major}.{current.minor}.{current.micro + 1}"
    new_text = re.sub(rf'("version"\s*:\s*"){re.escape(old)}"', rf'\g<1>{new}"', text, count=1)
    # guard against having replaced a nested `version` key
    if json.loads(new_text)["version"] != new:
        raise ValueError("Could not locate the top-level version in manifest.json")
    return new_text, new


def run(module: Path, *args: str) -> str:
    # hide the venv `uv run` created for this script, or poetry would use it as the project environment
    env = dict(os.environ)
    if venv := env.pop("VIRTUAL_ENV", None):
        venv_bin = os.path.join(venv, "bin")
        env["PATH"] = os.pathsep.join(p for p in env["PATH"].split(os.pathsep) if p != venv_bin)
    # poetry resolutions can take minutes: show what is running
    typer.echo(f"$ {' '.join(args)}")
    return subprocess.run(args, cwd=module, env=env, check=True, text=True, capture_output=True).stdout


def upgrade(module: Path, tool: str) -> list[str]:
    pyproject_path = module / "pyproject.toml"
    if tool == "poetry":
        pyproject_path.write_text(migrate_legacy_dev_dependencies(pyproject_path.read_text()))
    pyproject = tomllib.loads(pyproject_path.read_text())
    if tool == "uv":
        latest = parse_uv_outdated(run(module, "uv", "tree", "--outdated", "--depth", "1", "--all-groups"))
        dependencies = uv_dependencies(pyproject)
        refresh_lock = ("uv", "lock", "--upgrade")
    else:
        latest = parse_poetry_outdated(run(module, "poetry", "show", "--outdated", "--top-level", "--format", "json"))
        dependencies = poetry_dependencies(pyproject)
        refresh_lock = ("poetry", "update", "--lock")

    bumped = []
    for dependency in dependencies:
        version = latest.get(canonicalize_name(dependency.name))
        if version is None:
            continue
        if dependency.skip:
            typer.echo(f"Skip {dependency.name} ({dependency.skip}), latest is {version}")
            continue

        group = ["--group", dependency.group] if dependency.group else []
        if tool == "uv":
            command = ["uv", "add", "--no-sync", *group, uv_requirement(dependency, version)]
        else:
            command = ["poetry", "add", "--lock", *group, f"{dependency.name_with_extras}@latest"]

        # a failed resolution leaves pyproject.toml untouched, so carry on with the other dependencies
        before = pyproject_path.read_bytes()
        try:
            run(module, *command)
            if tool == "poetry" and declaration_count(tomllib.loads(pyproject_path.read_text()), dependency.name) != 1:
                pyproject_path.write_bytes(before)
                raise ValueError("poetry wrote a duplicate declaration")
            bumped.append(f"{dependency.name} -> {version}")
        except subprocess.CalledProcessError as error:
            # resolver errors are verbose: keep only the explaining line
            lines = error.stderr.strip().splitlines() or [""]
            reason = next((line.strip() for line in lines if "Because" in line), lines[-1].strip())
            typer.echo(f"Could not bump {dependency.name} to {version}: {reason}", err=True)
        except (ValueError, tomllib.TOMLDecodeError) as error:
            pyproject_path.write_bytes(before)
            typer.echo(f"Could not bump {dependency.name} to {version}: {error}", err=True)

    # refresh transitive dependencies
    run(module, *refresh_lock)
    return bumped


@app.command()
def main(module: Path = typer.Argument(..., help="Directory of the module, e.g. 1Password")):
    """Update the dependencies of a module, bump its version and add a CHANGELOG entry."""
    manifest, pyproject, changelog = module / "manifest.json", module / "pyproject.toml", module / "CHANGELOG.md"
    for path in (manifest, pyproject, changelog):
        if not path.is_file():
            typer.echo(f"Error: {path} not found", err=True)
            raise typer.Exit(1)

    lock = next((path for path in (module / "uv.lock", module / "poetry.lock") if path.is_file()), None)
    if lock is None:
        typer.echo(f"Error: no uv.lock or poetry.lock in {module}", err=True)
        raise typer.Exit(1)
    tool = lock.stem

    # turn `timeout`'s SIGTERM into SystemExit so the snapshot below gets restored
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    snapshot = {path: path.read_bytes() for path in (pyproject, lock)}
    try:
        bumped = upgrade(module, tool)
    except BaseException as error:
        # leave no half-updated module behind
        for path, content in snapshot.items():
            path.write_bytes(content)
        if isinstance(error, subprocess.CalledProcessError):
            typer.echo(f"Error: `{' '.join(error.cmd)}` failed:\n{error.stderr}", err=True)
            raise typer.Exit(1)
        raise

    # a migration of the pyproject.toml alone is not worth a release
    if not bumped and lock.read_bytes() == snapshot[lock]:
        pyproject.write_bytes(snapshot[pyproject])
    if all(path.read_bytes() == content for path, content in snapshot.items()):
        typer.echo(f"{module} dependencies are already up to date")
        return

    manifest_text, new_version = bump_manifest_version(manifest.read_text())
    changelog_lines = insert_new_version_entry(
        read_changelog(changelog), new_version, date.today().isoformat(), "Changed", "Update dependencies"
    )
    manifest.write_text(manifest_text)
    write_changelog(changelog, changelog_lines)

    typer.echo(f"✓ {module} ({tool}) updated to {new_version}")
    for line in bumped:
        typer.echo(f"  {line}")


if __name__ == "__main__":
    app()
