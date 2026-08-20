from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path
from typing import Any

# Support both package import and direct script execution.
try:
    from .display import banner, colorize
    from .environment import (
        auto_detect_module_dir,
        find_venv_python,
        inject_module_dir,
        install_module,
        module_is_importable,
        reexec_with_venv,
        resolve_module_dir,
        venv_has_core_deps,
    )
    from .runner import E2ERunner
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from e2e_runner.display import banner, colorize  # type: ignore[no-redef]
    from e2e_runner.environment import (  # type: ignore[no-redef]
        auto_detect_module_dir,
        find_venv_python,
        inject_module_dir,
        install_module,
        module_is_importable,
        reexec_with_venv,
        resolve_module_dir,
        venv_has_core_deps,
    )
    from e2e_runner.runner import E2ERunner  # type: ignore[no-redef]


def _prompt(label: str, default: str = "") -> str:
    suffix = f"  [{default}]" if default else ""
    value = input(colorize(f"  {label}{suffix}: ", "cyan")).strip()
    return value or default


def _wizard() -> tuple[dict[str, Any], Path, bool]:
    """
    Collect all required parameters interactively.
    Returns ``(runner_kwargs, module_dir, do_install)``.
    """
    banner("E2E Runner  –  Interactive Wizard")
    print(colorize(
        textwrap.dedent("""\
          Format for class references:
            dotted.module.path:ClassName
          Example:
            sophos_module.base:SophosModule
        """),
        "grey",
    ))

    detected = auto_detect_module_dir()
    default_dir = str(detected) if detected else ""
    raw_dir = _prompt("Module directory (folder containing the module package)", default=default_dir)
    module_dir = resolve_module_dir(raw_dir or None)

    do_install_str = _prompt("Install dependencies now? (y/N)", default="n")
    do_install = do_install_str.lower() in ("y", "yes")

    module_class_ref = _prompt("Module class  (e.g. sophos_module.base:SophosModule)")
    target_class_ref = _prompt(
        "Target class  (e.g. sophos_module.asset_connector.device_assets:SophosDeviceAssetConnector)"
    )

    print(colorize("\n  Component type:", "yellow"))
    print("    1) asset   – AssetConnector")
    print("    2) event   – Trigger / Connector")
    print("    3) action  – Action")
    print("    0) auto-detect (default)")
    choice = _prompt("Choose [0/1/2/3]", default="0")
    type_map: dict[str, str | None] = {"1": "asset", "2": "event", "3": "action", "0": None}
    connector_type = type_map.get(choice, None)

    print(colorize("\n  Module configuration:", "yellow"))
    print("    Enter as inline JSON or provide a file path.")
    mod_raw  = _prompt("Inline JSON  (or leave blank)", default="")
    mod_file = _prompt("Config file  (or leave blank)", default="") if not mod_raw else ""
    module_config = E2ERunner.load_config(mod_raw or None, mod_file or None)

    print(colorize("\n  Target configuration:", "yellow"))
    tgt_raw  = _prompt("Inline JSON  (or leave blank)", default="")
    tgt_file = _prompt("Config file  (or leave blank)", default="") if not tgt_raw else ""
    target_config = E2ERunner.load_config(tgt_raw or None, tgt_file or None)

    uuid      = _prompt("Connector configuration UUID", default="<YOUR_CONNECTOR_CONFIGURATION_UUID>")
    data_path = _prompt("Data path", default="./test_data")

    kwargs: dict[str, Any] = dict(
        module_class_ref=module_class_ref,
        target_class_ref=target_class_ref,
        module_config=module_config,
        target_config=target_config,
        connector_type=connector_type,
        data_path=Path(data_path),
        uuid=uuid,
    )
    return kwargs, module_dir, do_install


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
            # Asset connector (from the _utils repo)
            python -m _utils.e2e_runner \\
              --module-dir    ../Sophos \\
              --module-class  sophos_module.base:SophosModule \\
              --target-class  sophos_module.asset_connector.device_assets:SophosDeviceAssetConnector \\
              --module-config {\"client_id\":\"x\",\"client_secret":\"y\",\"api_host":\"https://...\"} \\
              --target-config {\"sekoia_api_key\":\"z\",\"sekoia_base_url\":\"https://...\",\"frequency\":60}

            # Trigger – configs from JSON files
            python -m _utils.e2e_runner \\
              --module-dir    ./Sophos \\
              --module-class  sophos_module.base:SophosModule \\
              --target-class  sophos_module.trigger_sophos_edr_events:SophosEDREventsTrigger \\
              --module-config ./secrets/module.json \\
              --target-config ./secrets/trigger.json \\
              --type event

            # First run: install deps automatically
            python -m _utils.e2e_runner --module-dir ./Sophos --install ...

            # Interactive wizard
            python -m _utils.e2e_runner --interactive
            """
        ),
    )

    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Launch the interactive wizard to fill parameters step by step.")
    parser.add_argument("--_venv-resolved", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--module-dir", metavar="PATH",
                        help=(
                            "Path to the module folder (e.g. ./Sophos). "
                            "Added to sys.path so its packages become importable. "
                            "Auto-detected from CWD if omitted."
                        ))
    parser.add_argument("--install", action="store_true",
                        help="Run `pip install -e <module-dir>` before importing. Useful on first run.")
    parser.add_argument("--module-class", metavar="MODULE:CLASS",
                        help="Dotted import path and class name of the Module.")
    parser.add_argument("--target-class", metavar="MODULE:CLASS",
                        help="Dotted import path and class name of the component to test.")
    parser.add_argument("--module-config", metavar="JSON_OR_FILE",
                        help="Module configuration as an inline JSON string or a path to a .json file.")
    parser.add_argument("--target-config", metavar="JSON_OR_FILE",
                        help="Connector/Trigger/Action configuration as an inline JSON string or .json file.")
    parser.add_argument("--type", metavar="TYPE", choices=["asset", "event", "action"],
                        help="Force the component type (asset / event / action). Auto-detected if omitted.")
    parser.add_argument("--uuid", metavar="UUID", default="<YOUR_CONNECTOR_CONFIGURATION_UUID>",
                        help="Connector configuration UUID.")
    parser.add_argument("--data-path", metavar="PATH", default="./test_data",
                        help="Directory used for persistent connector state (default: ./test_data).")
    parser.add_argument("--logs-url", metavar="URL", default=None,
                        help=(
                            "Sekoia logs URL (e.g. https://app.sekoia.io/api/v1/ingest/...)."
                            " Required for connectors that use OIDC role assumption (e.g. AWS)."
                        ))
    return parser


def _is_json_file(value: str) -> bool:
    return value.strip().endswith(".json") and not value.strip().startswith("{")


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

        module_dir = resolve_module_dir(args.module_dir)
        do_install = args.install

        def _resolve(value: str | None) -> dict[str, Any]:
            if not value:
                return {}
            if _is_json_file(value):
                return E2ERunner.load_config(None, value)
            return E2ERunner.load_config(value, None)

        runner_kwargs = dict(
            module_class_ref=args.module_class,
            target_class_ref=args.target_class,
            module_config=_resolve(args.module_config),
            target_config=_resolve(args.target_config),
            connector_type=args.type,
            data_path=Path(args.data_path),
            uuid=args.uuid,
            logs_url=args.logs_url,
        )

    if do_install and "--_venv-resolved" not in sys.argv:
        install_module(module_dir)

    reexec_with_venv(module_dir)

    if not module_is_importable(module_dir):
        venv_python = find_venv_python(module_dir)
        install_hint = (
            f"    cd {module_dir}\n"
            "    poetry install\n\n"
            "  Or let this tool install them automatically:\n\n"
            f"    python -m _utils.e2e_runner --module-dir {module_dir} --install ..."
        )
        if venv_python and not venv_has_core_deps(venv_python):
            install_hint = (
                "  The module venv exists but deps are not installed.\n\n"
                f"    cd {module_dir}\n"
                "    poetry install          # recommended\n\n"
                "  Or try (may fail if lock file is incompatible):\n\n"
                f"    python -m _utils.e2e_runner --module-dir {module_dir} --install ..."
            )
        print(colorize(
            "\n[ERROR] The module's dependencies are not installed in this environment.\n\n"
            "  Quick fix:\n\n" + install_hint + "\n",
            "red",
        ))
        sys.exit(1)

    inject_module_dir(module_dir)
    print(colorize(f"  Python  : {sys.executable}", "grey"))
    print(colorize(f"  sys.path ← {module_dir}", "grey"))

    E2ERunner(**runner_kwargs).run()


if __name__ == "__main__":
    import sys as _sys
    from pathlib import Path as _Path

    _pkg_root = str(_Path(__file__).parent.parent)
    if _pkg_root not in _sys.path:
        _sys.path.insert(0, _pkg_root)

    main()
