"""Guards the uv-only dependency setup.

The Dockerfile installs from ``uv.lock`` via ``uv sync --frozen``. If a
runtime dependency is declared in ``pyproject.toml`` but never resolves
into the lockfile, the image build silently installs the wrong set.
These tests catch that + the ``package = false`` marker that keeps the
project from accidentally being treated as a buildable wheel.
"""

import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parent.parent
UV_LOCK = REPO_ROOT / "uv.lock"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def _uv_versions() -> dict[str, str]:
    return {
        pkg["name"].lower(): pkg["version"]
        for pkg in _load(UV_LOCK)["package"]
        if "version" in pkg
    }


def test_uv_lock_is_committed():
    assert UV_LOCK.is_file(), "uv.lock is used by the Dockerfile (uv sync --frozen)"


def test_declared_runtime_dependencies_are_locked_by_uv():
    """Every runtime dep in ``[project].dependencies`` must appear in the
    lockfile — otherwise ``uv sync --frozen`` installs an incomplete set
    without failing the Docker build."""
    declared = _load(PYPROJECT)["project"]["dependencies"]
    # "sekoia-automation-sdk>=1.23.1,<2" -> "sekoia-automation-sdk"
    names = {
        d.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip().lower()
        for d in declared
    }
    assert names, "no runtime dependencies declared"

    uv_versions = _uv_versions()
    for name in names:
        assert name in uv_versions, f"{name} missing from uv.lock"


def test_requires_python_covers_sekoia_build_python():
    """Sekoia's pipeline ignores this repo's Dockerfile and runs its own
    uv install on its base image (3.12 as of 2026-07-28). A
    `requires-python` that excludes it fails the build outright, so the
    range has to stay wider than the 3.11 used locally."""
    spec = _load(PYPROJECT)["project"]["requires-python"]
    for version in ("3.11", "3.12"):
        assert Version(version) in SpecifierSet(spec), (
            f"requires-python={spec!r} excludes Python {version}; "
            f"Sekoia's builder cannot install the module"
        )


def test_project_is_not_a_distributable_package():
    """``main.py`` is the entrypoint; nothing imports this from outside the
    image. ``[tool.uv].package = false`` keeps uv from trying to build a
    wheel."""
    tool = _load(PYPROJECT)["tool"]
    assert tool["uv"]["package"] is False
