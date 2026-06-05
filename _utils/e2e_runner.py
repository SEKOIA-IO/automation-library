#!/usr/bin/env python3
"""
E2E Runner – Generic CLI tool to test any automation-library component.
=======================================================================

USAGE
-----
Run from anywhere – just point --module-dir to the module folder:

  python _utils/e2e_runner.py \\
    --module-dir   ./Sophos \\
    --module-class sophos_module.base:SophosModule \\
    --target-class sophos_module.asset_connector.device_assets:SophosDeviceAssetConnector \\
    --module-config '{"client_id":"x","client_secret":"y",...}' \\
    --target-config '{"sekoia_api_key":"z","frequency":60}' \\
    [--type asset|event|action]
    [--install]          # pip install -e <module-dir> before running
    [--uuid  "<uuid>"]
    [--data-path "./test_data"]

If you are ALREADY inside the module directory, --module-dir is auto-detected.

Interactive wizard (no flags needed):

  python _utils/e2e_runner.py --interactive

COMPONENT TYPES
---------------
  asset   – AssetConnector   → mocks push_assets_to_sekoia
  event   – Trigger/Connector → mocks send_event / send_records
  action  – Action            → mocks json_result / execute
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import PropertyMock, patch

# ──────────────────────────────────────────────────────────────────────────────
# Colour helpers (graceful fallback when NO_COLOR / non-tty)
# ──────────────────────────────────────────────────────────────────────────────
_USE_COLOUR = sys.stdout.isatty() and "NO_COLOR" not in __import__("os").environ

_COLOURS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "blue": "\033[34m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "grey": "\033[90m",
    "magenta": "\033[35m",
}


def _c(text: str, *styles: str) -> str:
    if not _USE_COLOUR:
        return text
    codes = "".join(_COLOURS.get(s, "") for s in styles)
    return f"{codes}{text}{_COLOURS['reset']}"


def _banner(title: str) -> None:
    line = "─" * 60
    print(_c(line, "blue"))
    print(_c(f"  {title}", "bold", "blue"))
    print(_c(line, "blue"))


# ──────────────────────────────────────────────────────────────────────────────
# Module directory resolution
# ──────────────────────────────────────────────────────────────────────────────

def _auto_detect_module_dir() -> Path | None:
    """
    Walk from the current directory upward looking for a pyproject.toml.
    Returns the first directory that contains one, or None.
    """
    current = Path.cwd()
    # Check CWD first, then parents (up to 3 levels)
    for candidate in [current, *current.parents[:3]]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return None


def _resolve_module_dir(raw: str | None) -> Path:
    """
    Return a resolved, existing module directory.
    Falls back to auto-detection if raw is None.
    """
    if raw:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            print(_c(f"[ERROR] --module-dir '{raw}' does not exist.", "red"))
            sys.exit(1)
        return path

    detected = _auto_detect_module_dir()
    if detected:
        print(_c(f"  Auto-detected module dir: {detected}", "grey"))
        return detected

    print(_c(
        "[ERROR] Could not auto-detect the module directory.\n"
        "  Run the tool from inside the module folder, or pass --module-dir <path>.",
        "red",
    ))
    sys.exit(1)


def _find_venv_python(module_dir: Path) -> Path | None:
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


def _venv_has_core_deps(venv_python: Path) -> bool:
    """
    Return True if the given Python interpreter has sekoia_automation installed.
    This is a lightweight probe to avoid re-execing into an empty/broken venv.
    """
    result = subprocess.run(
        [str(venv_python), "-c", "import sekoia_automation"],
        capture_output=True,
    )
    return result.returncode == 0


def _reexec_with_venv(module_dir: Path) -> None:
    """
    If the module has its own .venv that has deps installed, and we are NOT
    already running from it, re-execute this very script with that venv's
    Python (passing all original argv) and exit.

    Skips the re-exec when:
    - The sentinel --_venv-resolved is already in argv (loop guard)
    - No .venv found in the module directory
    - We are already running from that venv
    - The module venv is empty / deps not installed (avoids switching to a
      broken environment)

    A sentinel flag --_venv-resolved is appended to argv to prevent loops.
    """
    if "--_venv-resolved" in sys.argv:
        return  # already running inside the right venv

    venv_python = _find_venv_python(module_dir)
    if venv_python is None:
        return  # no local venv – keep going with current interpreter

    # Are we already using that venv?
    if Path(sys.executable).resolve() == venv_python.resolve():
        return

    # Only switch if the target venv actually has its dependencies installed.
    # An empty or broken venv is worse than the current interpreter.
    if not _venv_has_core_deps(venv_python):
        print(_c(
            f"  Module venv found ({venv_python.parent.parent.name}) "
            "but deps not installed – keeping current Python.",
            "grey",
        ))
        return

    print(_c(f"  Found module venv: {venv_python}", "grey"))
    print(_c("  Re-launching with module Python …\n", "grey"))
    new_argv = [str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:] + ["--_venv-resolved"]
    result = subprocess.run(new_argv)
    sys.exit(result.returncode)


def _install_module(module_dir: Path) -> None:
    """
    Install the module's dependencies inside module_dir.

    Strategy (tried in order):
      1. `poetry install --no-root` – preferred when pyproject.toml uses Poetry
      2. `pip install -r requirements.txt` – if a requirements.txt exists
      3. `pip install -e .` – generic fallback
    """
    print(_c(f"\n  Installing dependencies in {module_dir} …", "yellow"))

    # 1. Poetry
    if (module_dir / "pyproject.toml").exists():
        poetry = subprocess.run(
            ["poetry", "--version"], capture_output=True, cwd=str(module_dir)
        )
        if poetry.returncode == 0:
            result = subprocess.run(
                ["poetry", "install", "--no-root"],
                cwd=str(module_dir),
            )
            if result.returncode == 0:
                print(_c("  ✔  Dependencies installed (poetry).\n", "green"))
                return
            print(_c("  ⚠  poetry install failed – trying next method …", "yellow"))

    # 2. requirements.txt
    req_file = module_dir / "requirements.txt"
    if req_file.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"],
        )
        if result.returncode == 0:
            print(_c("  ✔  Dependencies installed (requirements.txt).\n", "green"))
            return
        print(_c("  ⚠  pip -r requirements.txt failed – trying pip install -e …", "yellow"))

    # 3. pip install -e (last resort)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(module_dir), "--quiet"],
    )
    if result.returncode != 0:
        print(_c(
            "[ERROR] All install methods failed.\n"
            f"  Please run `poetry install` manually inside {module_dir}.",
            "red",
        ))
        sys.exit(result.returncode)
    print(_c("  ✔  Dependencies installed (pip install -e).\n", "green"))


def _inject_module_dir(module_dir: Path) -> None:
    """Prepend module_dir to sys.path so its packages are importable."""
    path_str = str(module_dir)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


# ──────────────────────────────────────────────────────────────────────────────
# E2ERunner  –  main class
# ──────────────────────────────────────────────────────────────────────────────

class E2ERunner:
    """
    Main class to run end-to-end tests against any automation-library component.

    Public methods
    --------------
    run()                   – detect type and dispatch to the right runner
    run_asset_connector()   – test an AssetConnector
    run_event_connector()   – test a Trigger or generic Connector
    run_action()            – test an Action

    Private helpers
    ---------------
    _build_module()         – instantiate and configure the Module
    _build_connector()      – instantiate and configure the Connector/Trigger/Action
    _import_class()         – dynamic import from "module.path:ClassName"
    _detect_type()          – inspect MRO to decide component category
    _load_config()          – parse JSON string or file into a dict
    _print_log()            – coloured console logger (replaces the real .log())
    _print_summary()        – print final summary line
    """

    # ── construction ──────────────────────────────────────────────────────────

    def __init__(
        self,
        module_class_ref: str,
        target_class_ref: str,
        module_config: dict[str, Any],
        target_config: dict[str, Any],
        connector_type: str | None = None,
        data_path: Path = Path("./test_data"),
        uuid: str = "<YOUR_CONNECTOR_CONFIGURATION_UUID>",
    ) -> None:
        self.module_class_ref = module_class_ref
        self.target_class_ref = target_class_ref
        self.module_config = module_config
        self.target_config = target_config
        self.forced_type = connector_type
        self.data_path = data_path
        self.uuid = uuid

        # populated in run()
        self._module: Any = None
        self._connector: Any = None
        self._detected_type: str = "unknown"

    # ── public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Detect the component type and execute the appropriate test runner."""
        _banner("E2E Runner  –  automation-library")
        print(f"  Module  : {_c(self.module_class_ref, 'cyan')}")
        print(f"  Target  : {_c(self.target_class_ref, 'cyan')}")

        self._module = self._build_module()
        connector_cls = self._import_class(self.target_class_ref)
        self._detected_type = self.forced_type or self._detect_type(connector_cls)

        print(f"  Type    : {_c(self._detected_type, 'yellow', 'bold')}")
        print(f"  Data    : {_c(str(self.data_path), 'grey')}\n")

        dispatch = {
            "asset":  self.run_asset_connector,
            "event":  self.run_event_connector,
            "action": self.run_action,
        }

        runner = dispatch.get(self._detected_type)
        if runner is None:
            self._abort(
                f"Cannot run component of type '{self._detected_type}'.\n"
                f"  Supported types: asset, event, action.\n"
                f"  Use --type to override."
            )

        self._connector = self._build_connector(connector_cls)
        runner()  # type: ignore[operator]

    # ── public runner methods ─────────────────────────────────────────────────

    def run_asset_connector(self) -> None:
        """
        Test an AssetConnector.

        Mocks
        -----
        - push_assets_to_sekoia  → prints each OCSF asset
        - log                    → coloured console output
        - ModuleItem.logs_url    → None (no remote sink)
        """
        _banner("Running  AssetConnector")
        total_batches = 0
        total_assets = 0
        connector = self._connector

        def _on_push(assets: Any) -> None:
            nonlocal total_batches, total_assets
            items: list[Any] = getattr(assets, "items", [])
            total_batches += 1
            total_assets += len(items)
            print(
                _c(f"\n[BATCH #{total_batches}]", "green", "bold")
                + f" {len(items)} asset(s) would be pushed"
            )
            for asset in items:
                self._print_asset(asset)
            connector.update_checkpoint()

        with self._standard_patches(connector, extra={"push_assets_to_sekoia": _on_push}):
            connector.run()

        self._print_summary(f"{total_assets} asset(s) in {total_batches} batch(es)")

    def run_event_connector(self) -> None:
        """
        Test a Trigger or generic Connector.

        Mocks
        -----
        - send_event    → prints each event (Trigger)
        - send_records  → prints each records call (Connector)
        - log           → coloured console output
        - ModuleItem.logs_url → None
        """
        _banner("Running  EventConnector / Trigger")
        connector = self._connector
        event_count = 0
        records_count = 0

        def _on_send_event(event: Any) -> None:
            nonlocal event_count
            event_count += 1
            print(_c(f"[EVENT #{event_count}]", "green") + f" {event!r}")

        def _on_send_records(*args: Any, **kwargs: Any) -> None:
            nonlocal records_count
            records_count += 1
            size = len(args[0]) if args and hasattr(args[0], "__len__") else "?"
            print(_c(f"[RECORDS #{records_count}]", "green") + f" {size} record(s)  args={args!r}")

        extra: dict[str, Any] = {}
        if hasattr(connector, "send_event"):
            extra["send_event"] = _on_send_event
        if hasattr(connector, "send_records"):
            extra["send_records"] = _on_send_records

        with self._standard_patches(connector, extra=extra):
            connector.run()

        total = event_count + records_count
        self._print_summary(
            f"{total} call(s) intercepted  (events={event_count}, records={records_count})"
        )

    def run_action(self) -> None:
        """
        Test an Action.

        Mocks
        -----
        - json_result   → prints the action result
        - log           → coloured console output
        - ModuleItem.logs_url → None
        """
        _banner("Running  Action")
        connector = self._connector
        results: list[Any] = []

        def _on_result(result: Any) -> None:
            results.append(result)
            print(
                _c(f"[RESULT #{len(results)}]", "green")
                + f"\n{json.dumps(result, indent=2, default=str)}"
            )

        with self._standard_patches(connector, extra={"json_result": _on_result}):
            connector.execute()

        self._print_summary(f"{len(results)} result(s)")

    # ── private helpers ───────────────────────────────────────────────────────

    def _build_module(self) -> Any:
        """Instantiate and configure the Module."""
        module_cls = self._import_class(self.module_class_ref)
        module = module_cls()
        module.configuration = self.module_config
        return module

    def _build_connector(self, connector_cls: type) -> Any:
        """Instantiate and configure the Connector / Trigger / Action."""
        self.data_path.mkdir(parents=True, exist_ok=True)

        if self._detected_type == "action":
            instance = connector_cls(module=self._module)
        else:
            instance = connector_cls(module=self._module, data_path=self.data_path)
            instance.configuration = self.target_config

        instance.module._connector_configuration_uuid = self.uuid
        return instance

    def _import_class(self, class_ref: str) -> type:
        """
        Import a class from a 'dotted.module.path:ClassName' reference.
        Falls back to 'dotted.module.path.ClassName' (dot-only) notation.
        """
        if ":" in class_ref:
            module_path, class_name = class_ref.rsplit(":", 1)
        elif "." in class_ref:
            module_path, class_name = class_ref.rsplit(".", 1)
        else:
            self._abort(
                f"Invalid class reference '{class_ref}'. Use 'module.path:ClassName'."
            )

        try:
            mod = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            self._abort(
                f"Cannot import '{module_path}': {exc}\n\n"
                f"  Possible fixes:\n"
                f"  1. Pass --module-dir pointing to the module folder\n"
                f"     e.g.  --module-dir ./Sophos\n"
                f"  2. Add --install to install the module's dependencies first\n"
                f"  3. Make sure you run with the right Python interpreter\n"
                f"     (the one that has sekoia_automation installed)"
            )

        cls = getattr(mod, class_name, None)
        if cls is None:
            self._abort(f"Class '{class_name}' not found in '{module_path}'.")

        return cls  # type: ignore[return-value]

    def _detect_type(self, connector_cls: type) -> str:
        """
        Inspect the MRO of the class to determine the component category.

        Returns
        -------
        'asset'   – inherits from AssetConnector
        'event'   – inherits from Trigger or Connector
        'action'  – inherits from Action
        'unknown' – none of the above
        """
        mro_names = {c.__name__ for c in connector_cls.__mro__}
        if "AssetConnector" in mro_names:
            return "asset"
        if "Action" in mro_names:
            return "action"
        if "Trigger" in mro_names or "Connector" in mro_names:
            return "event"
        return "unknown"

    @staticmethod
    def _load_config(value: str | None, file_path: str | None) -> dict[str, Any]:
        """
        Load a configuration dict from either a raw JSON string or a JSON file.
        Returns an empty dict if both are None.
        """
        if file_path:
            path = Path(file_path)
            if not path.exists():
                print(_c(f"[ERROR] Config file not found: {file_path}", "red"))
                sys.exit(1)
            return json.loads(path.read_text())
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                print(_c(f"[ERROR] Invalid JSON for config: {exc}", "red"))
                sys.exit(1)
        return {}

    def _print_log(self, message: str, level: str = "info", **_: Any) -> None:
        """Coloured log handler injected in place of connector.log().
        Extra kwargs (e.g. propagate=False) are silently ignored.
        """
        colour_map = {
            "debug":    "grey",
            "info":     "cyan",
            "warning":  "yellow",
            "error":    "red",
            "critical": "red",
        }
        colour = colour_map.get(level.lower(), "cyan")
        tag = _c(f"[{level.upper():8}]", colour)
        print(f"{tag} {message}")

    def _print_asset(self, asset: Any) -> None:
        """Pretty-print a single OCSF asset."""
        device  = getattr(asset, "device", None)
        user    = getattr(asset, "user", None)
        product = getattr(asset, "product", None)
        vuln    = getattr(asset, "finding", None)

        if device:
            uid      = getattr(device, "uid", "?")
            hostname = getattr(device, "hostname", "?")
            last_seen = getattr(device, "last_seen_time", "?")
            print(f"    {_c('●', 'green')} uid={uid}  hostname={hostname}  last_seen={last_seen}")
        elif user:
            uid   = getattr(user, "uid", "?")
            name  = getattr(user, "name", "?")
            email = getattr(user, "email_addr", "")
            print(f"    {_c('●', 'green')} uid={uid}  name={name}  email={email}")
        elif product:
            name    = getattr(product, "name", "?")
            version = getattr(product, "version", "?")
            print(f"    {_c('●', 'green')} name={name}  version={version}")
        elif vuln:
            cve = getattr(vuln, "uid", "?")
            print(f"    {_c('●', 'green')} cve={cve}")
        else:
            print(f"    {_c('●', 'green')} {asset!r}")

    def _standard_patches(self, connector: Any, extra: dict[str, Any]) -> Any:
        """
        Context manager that applies the standard set of mocks plus any
        extra {method_name: side_effect} overrides for the given connector.
        """
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(
            patch(
                "sekoia_automation.module.ModuleItem.logs_url",
                new_callable=PropertyMock,
                return_value=None,
            )
        )
        stack.enter_context(
            patch.object(connector, "log", side_effect=self._print_log)
        )
        for method_name, side_effect in extra.items():
            stack.enter_context(
                patch.object(connector, method_name, side_effect=side_effect)
            )
        return stack

    @staticmethod
    def _print_summary(message: str) -> None:
        print("\n" + _c("─" * 60, "blue"))
        print(_c(f"  ✔  {message}", "green", "bold"))
        print(_c("─" * 60, "blue") + "\n")

    @staticmethod
    def _abort(message: str) -> None:
        print(_c(f"\n[ERROR] {message}", "red"))
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Interactive wizard
# ──────────────────────────────────────────────────────────────────────────────

def _prompt(label: str, default: str = "") -> str:
    suffix = f"  [{default}]" if default else ""
    value = input(_c(f"  {label}{suffix}: ", "cyan")).strip()
    return value or default


def _wizard() -> tuple[dict[str, Any], Path, bool]:
    """
    Collect all required parameters interactively.
    Returns (runner_kwargs, module_dir, do_install).
    """
    _banner("E2E Runner  –  Interactive Wizard")
    print(
        _c(
            textwrap.dedent("""\
              Format for class references:
                dotted.module.path:ClassName
              Example:
                sophos_module.base:SophosModule
            """),
            "grey",
        )
    )

    # ── Module directory ─────────────────────────────────────────────────────
    detected = _auto_detect_module_dir()
    default_dir = str(detected) if detected else ""
    raw_dir = _prompt("Module directory (folder containing the module package)", default=default_dir)
    module_dir = _resolve_module_dir(raw_dir or None)

    do_install_str = _prompt("Install dependencies now? (y/N)", default="n")
    do_install = do_install_str.lower() in ("y", "yes")

    # ── Classes ───────────────────────────────────────────────────────────────
    module_class_ref = _prompt("Module class  (e.g. sophos_module.base:SophosModule)")
    target_class_ref = _prompt(
        "Target class  (e.g. sophos_module.asset_connector.device_assets:SophosDeviceAssetConnector)"
    )

    # ── Component type ────────────────────────────────────────────────────────
    print(_c("\n  Component type:", "yellow"))
    print("    1) asset   – AssetConnector")
    print("    2) event   – Trigger / Connector")
    print("    3) action  – Action")
    print("    0) auto-detect (default)")
    choice = _prompt("Choose [0/1/2/3]", default="0")
    type_map = {"1": "asset", "2": "event", "3": "action", "0": None}
    connector_type = type_map.get(choice, None)

    # ── Module config ─────────────────────────────────────────────────────────
    print(_c("\n  Module configuration:", "yellow"))
    print("    Enter as inline JSON or provide a file path.")
    mod_raw  = _prompt("Inline JSON  (or leave blank)", default="")
    mod_file = _prompt("Config file  (or leave blank)", default="") if not mod_raw else ""
    module_config = E2ERunner._load_config(mod_raw or None, mod_file or None)

    # ── Target config ─────────────────────────────────────────────────────────
    print(_c("\n  Target configuration:", "yellow"))
    tgt_raw  = _prompt("Inline JSON  (or leave blank)", default="")
    tgt_file = _prompt("Config file  (or leave blank)", default="") if not tgt_raw else ""
    target_config = E2ERunner._load_config(tgt_raw or None, tgt_file or None)

    uuid      = _prompt("Connector configuration UUID", default="<YOUR_CONNECTOR_CONFIGURATION_UUID>")
    data_path = _prompt("Data path", default="./test_data")

    kwargs = dict(
        module_class_ref=module_class_ref,
        target_class_ref=target_class_ref,
        module_config=module_config,
        target_config=target_config,
        connector_type=connector_type,
        data_path=Path(data_path),
        uuid=uuid,
    )
    return kwargs, module_dir, do_install


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="e2e_runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            Generic E2E test runner for automation-library components.

            Point --module-dir to the module folder so its packages are
            importable, then specify the classes and configurations.

            Examples
            --------
            # Asset connector (from the repo root)
            python _utils/e2e_runner.py \\
              --module-dir    ./Sophos \\
              --module-class  sophos_module.base:SophosModule \\
              --target-class  sophos_module.asset_connector.device_assets:SophosDeviceAssetConnector \\
              --module-config '{"client_id":"x","client_secret":"y","api_host":"https://...","oauth2_authorization_url":"https://..."}' \\
              --target-config '{"sekoia_api_key":"z","sekoia_base_url":"https://...","frequency":60}'

            # Trigger – configs from JSON files
            python _utils/e2e_runner.py \\
              --module-dir    ./Sophos \\
              --module-class  sophos_module.base:SophosModule \\
              --target-class  sophos_module.trigger_sophos_edr_events:SophosEDREventsTrigger \\
              --module-config ./secrets/module.json \\
              --target-config ./secrets/trigger.json \\
              --type event

            # First run: install deps automatically
            python _utils/e2e_runner.py --module-dir ./Sophos --install ...

            # Interactive wizard
            python _utils/e2e_runner.py --interactive
            """
        ),
    )

    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Launch the interactive wizard to fill parameters step by step.",
    )
    # Internal sentinel – set automatically when the script re-execs itself
    # with the module's own .venv Python. Never pass this manually.
    parser.add_argument("--_venv-resolved", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--module-dir", metavar="PATH",
        help=(
            "Path to the module folder (e.g. ./Sophos). "
            "Added to sys.path so its packages become importable. "
            "Auto-detected from CWD if omitted."
        ),
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Run `pip install -e <module-dir>` before importing. Useful on first run.",
    )
    parser.add_argument(
        "--module-class", metavar="MODULE:CLASS",
        help="Dotted import path and class name of the Module, e.g. sophos_module.base:SophosModule",
    )
    parser.add_argument(
        "--target-class", metavar="MODULE:CLASS",
        help="Dotted import path and class name of the component to test.",
    )
    parser.add_argument(
        "--module-config", metavar="JSON_OR_FILE",
        help="Module configuration as an inline JSON string or a path to a .json file.",
    )
    parser.add_argument(
        "--target-config", metavar="JSON_OR_FILE",
        help="Connector/Trigger/Action configuration as an inline JSON string or .json file.",
    )
    parser.add_argument(
        "--type", metavar="TYPE",
        choices=["asset", "event", "action"],
        help="Force the component type (asset / event / action). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--uuid", metavar="UUID",
        default="<YOUR_CONNECTOR_CONFIGURATION_UUID>",
        help="Connector configuration UUID.",
    )
    parser.add_argument(
        "--data-path", metavar="PATH",
        default="./test_data",
        help="Directory used for persistent connector state (default: ./test_data).",
    )
    return parser


def _is_json_file(value: str) -> bool:
    return value.strip().endswith(".json") and not value.strip().startswith("{")


def _module_is_importable(module_dir: Path) -> bool:
    """
    Quick heuristic: try importing a minimal dependency (sekoia_automation)
    to decide whether the module's venv has its deps installed.
    Returns True if importable, False otherwise.
    """
    try:
        importlib.import_module("sekoia_automation")
        return True
    except ModuleNotFoundError:
        return False


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.interactive:
        runner_kwargs, module_dir, do_install = _wizard()
    else:
        if not args.module_class or not args.target_class:
            parser.error(
                "You must provide --module-class and --target-class, "
                "or use --interactive."
            )

        module_dir = _resolve_module_dir(args.module_dir)
        do_install = args.install

        def _resolve(value: str | None) -> dict[str, Any]:
            if not value:
                return {}
            if _is_json_file(value):
                return E2ERunner._load_config(None, value)
            return E2ERunner._load_config(value, None)

        runner_kwargs = dict(
            module_class_ref=args.module_class,
            target_class_ref=args.target_class,
            module_config=_resolve(args.module_config),
            target_config=_resolve(args.target_config),
            connector_type=args.type,
            data_path=Path(args.data_path),
            uuid=args.uuid,
        )

    # ── setup environment ─────────────────────────────────────────────────────
    # 1. If --install was requested, install deps first (before any re-exec).
    #    This way, the subsequent venv probe will find the deps and re-exec
    #    into the (now populated) module venv.
    if do_install and "--_venv-resolved" not in sys.argv:
        _install_module(module_dir)

    # 2. If the module has a populated .venv, transparently re-exec with it.
    _reexec_with_venv(module_dir)

    # 3. Verify deps are importable in the current interpreter.
    if not _module_is_importable(module_dir):
        venv_python = _find_venv_python(module_dir)
        install_hint = (
            f"    cd {module_dir}\n"
            "    poetry install\n\n"
            "  Or let this tool install them automatically:\n\n"
            f"    python _utils/e2e_runner.py --module-dir {module_dir} --install ..."
        )
        if venv_python and not _venv_has_core_deps(venv_python):
            install_hint = (
                f"  The module venv exists but deps are not installed.\n\n"
                f"    cd {module_dir}\n"
                "    poetry install          # recommended\n\n"
                "  Or try (may fail if lock file is incompatible):\n\n"
                f"    python _utils/e2e_runner.py --module-dir {module_dir} --install ..."
            )
        print(_c(
            "\n[ERROR] The module's dependencies are not installed in this environment.\n\n"
            "  Quick fix:\n\n" + install_hint + "\n",
            "red",
        ))
        sys.exit(1)

    # 4. Add module root to sys.path so its packages are importable.
    _inject_module_dir(module_dir)
    print(_c(f"  Python  : {sys.executable}", "grey"))
    print(_c(f"  sys.path ← {module_dir}", "grey"))

    # ── run ───────────────────────────────────────────────────────────────────
    runner = E2ERunner(**runner_kwargs)
    runner.run()


if __name__ == "__main__":
    main()

