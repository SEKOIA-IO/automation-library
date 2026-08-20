from __future__ import annotations

from importlib import import_module
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import PropertyMock, patch

from .display import banner, colorize


class E2ERunner:
    """
    Run end-to-end tests against any automation-library component.

    Public methods
    --------------
    run()                   – detect type and dispatch to the right runner
    run_asset_connector()   – test an AssetConnector
    run_event_connector()   – test a Trigger or generic Connector
    run_action()            – test an Action
    """

    def __init__(
        self,
        module_class_ref: str,
        target_class_ref: str,
        module_config: dict[str, Any],
        target_config: dict[str, Any],
        connector_type: str | None = None,
        data_path: Path = Path("./test_data"),
        uuid: str = "<YOUR_CONNECTOR_CONFIGURATION_UUID>",
        logs_url: str | None = None,
    ) -> None:
        self.module_class_ref = module_class_ref
        self.target_class_ref = target_class_ref
        self.module_config = module_config
        self.target_config = target_config
        self.forced_type = connector_type
        self.data_path = data_path
        self.uuid = uuid
        self.logs_url = logs_url

        self._module: Any = None
        self._connector: Any = None
        self._detected_type: str = "unknown"

    def run(self) -> None:
        """Detect the component type and execute the appropriate test runner."""
        banner("E2E Runner  –  automation-library")
        print(f"  Module  : {colorize(self.module_class_ref, 'cyan')}")
        print(f"  Target  : {colorize(self.target_class_ref, 'cyan')}")

        self._module = self._build_module()
        connector_cls = self._import_class(self.target_class_ref)
        self._detected_type = self.forced_type or self._detect_type(connector_cls)

        print(f"  Type    : {colorize(self._detected_type, 'yellow', 'bold')}")
        print(f"  Data    : {colorize(str(self.data_path), 'grey')}\n")

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

    def run_asset_connector(self) -> None:
        """
        Test an AssetConnector.

        Mocks: push_assets_to_sekoia → prints each OCSF asset; log → coloured output.
        """
        banner("Running  AssetConnector")
        total_batches = 0
        total_assets = 0
        connector = self._connector

        def _on_push(assets: Any) -> None:
            nonlocal total_batches, total_assets
            items: list[Any] = getattr(assets, "items", [])
            total_batches += 1
            total_assets += len(items)
            print(
                colorize(f"\n[BATCH #{total_batches}]", "green", "bold")
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

        Mocks: send_event / send_records → prints intercepted calls; log → coloured output.
        """
        banner("Running  EventConnector / Trigger")
        connector = self._connector
        event_count = 0
        records_count = 0

        def _on_send_event(event: Any) -> None:
            nonlocal event_count
            event_count += 1
            print(colorize(f"[EVENT #{event_count}]", "green") + f" {event!r}")

        def _on_send_records(*args: Any, **kwargs: Any) -> None:
            nonlocal records_count
            records_count += 1
            size = len(args[0]) if args and hasattr(args[0], "__len__") else "?"
            print(colorize(f"[RECORDS #{records_count}]", "green") + f" {size} record(s)  args={args!r}")

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

        Calls connector.run(target_config) directly and prints the returned result.
        Mocks: log → coloured output.
        """
        banner("Running  Action")
        action = self._connector

        with self._standard_patches(action, extra={}):
            result = action.run(self.target_config)

        print(colorize("[RESULT]", "green"))
        print(json.dumps(result, indent=2, default=str))

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
        Import a class from a ``dotted.module.path:ClassName`` reference.
        Also accepts dot-only notation (``dotted.module.path.ClassName``).
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
            mod = import_module(module_path)
        except ModuleNotFoundError as exc:
            self._abort(
                f"Cannot import '{module_path}': {exc}"
            )

        cls = getattr(mod, class_name, None)
        if cls is None:
            self._abort(f"Class '{class_name}' not found in '{module_path}'.")

        return cls  # type: ignore[return-value]

    def _detect_type(self, connector_cls: type) -> str:
        """
        Inspect the all parent classes to determine the component category.

        Returns ``'asset'``, ``'event'``, ``'action'``, or ``'unknown'``.
        """
        parent_class_names = {c.__name__ for c in connector_cls.__mro__}
        if "AssetConnector" in parent_class_names:
            return "asset"
        if "Action" in parent_class_names:
            return "action"
        if "Trigger" in parent_class_names or "Connector" in parent_class_names:
            return "event"
        return "unknown"

    @staticmethod
    def load_config(value: str | None, file_path: str | None) -> dict[str, Any]:
        """
        Load a configuration dict from either a raw JSON string or a JSON file.
        Returns an empty dict if both are None.
        """
        if file_path:
            path = Path(file_path)
            if not path.exists():
                print(colorize(f"[ERROR] Config file not found: {file_path}", "red"))
                sys.exit(1)
            return json.loads(path.read_text())
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                print(colorize(f"[ERROR] Invalid JSON for config: {exc}", "red"))
                sys.exit(1)
        return {}

    def _print_log(self, message: str, level: str = "info", **_: Any) -> None:
        """Coloured log handler injected in place of connector.log()."""
        colour_map = {
            "debug":    "grey",
            "info":     "cyan",
            "warning":  "yellow",
            "error":    "red",
            "critical": "red",
        }
        colour = colour_map.get(level.lower(), "cyan")
        tag = colorize(f"[{level.upper():8}]", colour)
        print(f"{tag} {message}")

    def _print_asset(self, asset: Any) -> None:
        """Pretty-print a single OCSF asset."""
        device  = getattr(asset, "device", None)
        user    = getattr(asset, "user", None)
        product = getattr(asset, "product", None)
        vuln    = getattr(asset, "finding", None)

        if device:
            uid       = getattr(device, "uid", "?")
            hostname  = getattr(device, "hostname", "?")
            last_seen = getattr(device, "last_seen_time", "?")
            print(f"    {colorize('●', 'green')} uid={uid}  hostname={hostname}  last_seen={last_seen}")
        elif user:
            uid   = getattr(user, "uid", "?")
            name  = getattr(user, "name", "?")
            email = getattr(user, "email_addr", "")
            print(f"    {colorize('●', 'green')} uid={uid}  name={name}  email={email}")
        elif product:
            name    = getattr(product, "name", "?")
            version = getattr(product, "version", "?")
            print(f"    {colorize('●', 'green')} name={name}  version={version}")
        elif vuln:
            cve = getattr(vuln, "uid", "?")
            print(f"    {colorize('●', 'green')} cve={cve}")
        else:
            print(f"    {colorize('●', 'green')} {asset!r}")

    def _standard_patches(self, connector: Any, extra: dict[str, Any]) -> ExitStack:
        """
        Context manager that applies standard mocks plus any extra
        ``{method_name: side_effect}`` overrides for the given connector.
        """
        stack = ExitStack()
        stack.enter_context(
            patch(
                "sekoia_automation.module.ModuleItem.logs_url",
                new_callable=PropertyMock,
                return_value=self.logs_url,
            )
        )
        stack.enter_context(patch.object(connector, "log", side_effect=self._print_log))
        for method_name, side_effect in extra.items():
            stack.enter_context(patch.object(connector, method_name, side_effect=side_effect))
        return stack

    @staticmethod
    def _print_summary(message: str) -> None:
        print("\n" + colorize("─" * 60, "blue"))
        print(colorize(f"  ✔  {message}", "green", "bold"))
        print(colorize("─" * 60, "blue") + "\n")

    @staticmethod
    def _abort(message: str) -> None:
        print(colorize(f"\n[ERROR] {message}", "red"))
        sys.exit(1)
