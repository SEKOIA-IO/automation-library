"""Guards the dual uv + poetry dependency setup.

The module ships two lockfiles because the two consumers want different
things: the Dockerfile (and local development) installs from ``uv.lock``,
while Sekoia's module importer rejects a module that doesn't ship a
``poetry.lock``. Two resolvers over one dependency set drift silently — the
first generation of this pair already disagreed on a transitive package —
so the agreement is asserted here rather than left to whoever remembers to
run both ``lock`` commands.
"""

import tomllib
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parent.parent
UV_LOCK = REPO_ROOT / "uv.lock"
POETRY_LOCK = REPO_ROOT / "poetry.lock"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def _poetry_runtime_versions() -> dict[str, str]:
    """``{name: version}`` for poetry's ``main`` group — what the image would
    install. Dev-only packages are excluded; they never reach the runtime."""
    return {
        pkg["name"].lower(): pkg["version"]
        for pkg in _load(POETRY_LOCK)["package"]
        if "main" in pkg.get("groups", [])
    }


def _uv_versions() -> dict[str, str]:
    return {
        pkg["name"].lower(): pkg["version"]
        for pkg in _load(UV_LOCK)["package"]
        if "version" in pkg
    }


def test_both_lockfiles_are_committed():
    assert UV_LOCK.is_file(), "uv.lock is used by the Dockerfile"
    assert POETRY_LOCK.is_file(), "poetry.lock is required by Sekoia's importer"


def test_lockfiles_agree_on_runtime_versions():
    """Every runtime package poetry resolves must be pinned to the same
    version in uv.lock. A mismatch means the image and the published module
    disagree about what gets installed; fix with `uv lock && poetry lock`."""
    poetry_versions = _poetry_runtime_versions()
    uv_versions = _uv_versions()

    mismatched = {
        name: (version, uv_versions.get(name))
        for name, version in poetry_versions.items()
        if uv_versions.get(name) != version
    }
    assert not mismatched, (
        "poetry.lock and uv.lock disagree on runtime packages "
        f"(name: (poetry, uv)): {mismatched}"
    )


def test_declared_runtime_dependencies_are_locked_by_both():
    """Sanity-check the comparison above is actually covering the direct
    dependencies, not silently comparing an empty intersection."""
    declared = _load(PYPROJECT)["project"]["dependencies"]
    # "APScheduler>=3.10,<4" -> "apscheduler"
    names = {
        d.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip().lower()
        for d in declared
    }
    assert names, "no runtime dependencies declared"

    poetry_versions = _poetry_runtime_versions()
    uv_versions = _uv_versions()
    for name in names:
        assert name in poetry_versions, f"{name} missing from poetry.lock main group"
        assert name in uv_versions, f"{name} missing from uv.lock"


def test_dev_dependency_lists_are_kept_in_sync():
    """The dev list is declared twice — PEP 735 `[dependency-groups]` for uv,
    `[tool.poetry.group.dev.dependencies]` for poetry 2.1, which doesn't read
    PEP 735 groups. Nothing but this test keeps the duplicates honest."""
    pyproject = _load(PYPROJECT)

    uv_dev = {
        d.split(">")[0].split("<")[0].split("=")[0].strip().lower()
        for d in pyproject["dependency-groups"]["dev"]
    }
    poetry_dev = {
        name.lower()
        for name in pyproject["tool"]["poetry"]["group"]["dev"]["dependencies"]
    }

    assert uv_dev == poetry_dev, (
        "dev dependencies differ between [dependency-groups].dev (uv) and "
        f"[tool.poetry.group.dev.dependencies] (poetry): "
        f"uv-only={uv_dev - poetry_dev}, poetry-only={poetry_dev - uv_dev}"
    )


def test_requires_python_covers_sekoia_build_python():
    """Sekoia's pipeline ignores this repo's Dockerfile and runs
    `poetry install` on its own base image (currently 3.12). A
    `requires-python` that excludes it fails the build outright, so the range
    has to stay wider than the 3.11 used locally."""
    spec = _load(PYPROJECT)["project"]["requires-python"]
    for version in ("3.11", "3.12"):
        assert Version(version) in SpecifierSet(spec), (
            f"requires-python={spec!r} excludes Python {version}; "
            f"Sekoia's builder cannot install the module"
        )


@pytest.mark.parametrize("marker", ["package-mode", "package"])
def test_project_is_not_a_distributable_package_for_either_tool(marker):
    """`main.py` is the entrypoint; nothing imports this from outside the
    image. Both tools must agree, or one of them tries to build a wheel with
    the other's backend."""
    tool = _load(PYPROJECT)["tool"]
    if marker == "package-mode":
        assert tool["poetry"]["package-mode"] is False
    else:
        assert tool["uv"]["package"] is False
