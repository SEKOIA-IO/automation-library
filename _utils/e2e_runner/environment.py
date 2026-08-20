"""Module directory resolution, venv detection, and dependency installation."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

from .display import colorize


def auto_detect_module_dir() -> Path | None:
    """
    Walk from the current directory upward looking for a pyproject.toml.
    Returns the first directory that contains one, or None.
    """
    current = Path.cwd()
    for candidate in [current, *current.parents[:3]]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return None


def resolve_module_dir(raw: str | None) -> Path:
    """Return a resolved, existing module directory. Falls back to auto-detection."""
    if raw:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            print(colorize(f"[ERROR] --module-dir '{raw}' does not exist.", "red"))
            sys.exit(1)
        return path

    detected = auto_detect_module_dir()
    if detected:
        print(colorize(f"  Auto-detected module dir: {detected}", "grey"))
        return detected

    print(colorize(
        "[ERROR] Could not auto-detect the module directory.\n"
        "  Run the tool from inside the module folder, or pass --module-dir <path>.",
        "red",
    ))
    sys.exit(1)


def find_venv_python(module_dir: Path) -> Path | None:
    """
    Return the path to the Python interpreter inside the module's .venv,
    or None if no .venv exists.
    Supports POSIX (.venv/bin/python) and Windows (.venv/Scripts/python.exe).
    """
    for candidate in [
        module_dir / ".venv" / "bin" / "python",
        module_dir / ".venv" / "Scripts" / "python.exe",
    ]:
        if candidate.exists():
            return candidate
    return None


def venv_has_core_deps(venv_python: Path) -> bool:
    """Return True if the given Python interpreter has sekoia_automation installed."""
    result = subprocess.run(
        [str(venv_python), "-c", "import sekoia_automation"],
        capture_output=True,
    )
    return result.returncode == 0


def reexec_with_venv(module_dir: Path) -> None:
    """
    If the module has its own populated .venv and we are NOT already running from it,
    re-execute this script with that venv's Python and exit.

    A sentinel flag --_venv-resolved is appended to argv to prevent loops.
    """
    if "--_venv-resolved" in sys.argv:
        return

    venv_python = find_venv_python(module_dir)
    if venv_python is None:
        return

    if Path(sys.executable).resolve() == venv_python.resolve():
        return

    if not venv_has_core_deps(venv_python):
        print(colorize(
            f"  Module venv found ({venv_python.parent.parent.name}) "
            "but deps not installed – keeping current Python.",
            "grey",
        ))
        return

    print(colorize(f"  Found module venv: {venv_python}", "grey"))
    print(colorize("  Re-launching with module Python …\n", "grey"))
    new_argv = [str(venv_python), str(Path(sys.argv[0]).resolve())] + sys.argv[1:] + ["--_venv-resolved"]
    result = subprocess.run(new_argv)
    sys.exit(result.returncode)


def install_module(module_dir: Path) -> None:
    """
    Install the module's dependencies inside module_dir.

    Strategy (tried in order):
      1. ``poetry install --no-root`` – preferred when pyproject.toml uses Poetry
      2. ``pip install -r requirements.txt`` – if a requirements.txt exists
      3. ``pip install -e .`` – generic fallback
    """
    print(colorize(f"\n  Installing dependencies in {module_dir} …", "yellow"))

    if (module_dir / "pyproject.toml").exists():
        poetry = subprocess.run(
            ["poetry", "--version"], capture_output=True, cwd=str(module_dir)
        )
        if poetry.returncode == 0:
            result = subprocess.run(["poetry", "install", "--no-root"], cwd=str(module_dir))
            if result.returncode == 0:
                print(colorize("  ✔  Dependencies installed (poetry).\n", "green"))
                return
            print(colorize("  ⚠  poetry install failed – trying next method …", "yellow"))

    req_file = module_dir / "requirements.txt"
    if req_file.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"],
        )
        if result.returncode == 0:
            print(colorize("  ✔  Dependencies installed (requirements.txt).\n", "green"))
            return
        print(colorize("  ⚠  pip -r requirements.txt failed – trying pip install -e …", "yellow"))

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(module_dir), "--quiet"],
    )
    if result.returncode != 0:
        print(colorize(
            "[ERROR] All install methods failed.\n"
            f"  Please run `poetry install` manually inside {module_dir}.",
            "red",
        ))
        sys.exit(result.returncode)
    print(colorize("  ✔  Dependencies installed (pip install -e).\n", "green"))


def inject_module_dir(module_dir: Path) -> None:
    """Prepend module_dir to sys.path so its packages are importable."""
    path_str = str(module_dir)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def module_is_importable(module_dir: Path) -> bool:  # noqa: ARG001
    """
    Quick heuristic: try importing sekoia_automation to verify the environment
    has its dependencies installed.
    """
    try:
        importlib.import_module("sekoia_automation")
        return True
    except ModuleNotFoundError:
        return False
