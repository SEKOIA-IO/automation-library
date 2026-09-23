"""Descriptor drift test, generalised across the whole module.

tests/test_trigger_sandbox_completed.py carries a single hand-written check
comparing trigger_sandbox_completed.json against SandboxCompletedConfiguration,
because the two had silently diverged and a customer would have had a valid
looking value rejected. This file generalises that check to every action,
trigger and connector descriptor: every declared default, minimum and maximum
must match the pydantic model behind it, every declared argument must exist
on the model, and every model field must appear in the descriptor.

Descriptors and models are discovered, not hard coded, so this keeps working
as actions, triggers and connectors are added or changed:

1. main.py is read with `ast` (not imported, since its registration calls sit
   under `if __name__ == "__main__":`) to recover the ground truth mapping
   from a descriptor's `docker_parameters` to the class Sekoia will run.
2. Every polyswarm_modules submodule is imported, and every class it defines
   locally is indexed by name, which locates the submodule that defines the
   registered class.
3. Inside that submodule, the pydantic model describing the descriptor's
   `arguments` is the one locally defined class whose name ends in
   "Arguments" or "Configuration", which is the naming convention every
   action, trigger and connector in this module already follows.

A descriptor whose `docker_parameters` is not registered in main.py, or whose
submodule carries no single Arguments/Configuration model, fails loudly
instead of being skipped, since a silent skip here is exactly the kind of gap
this test exists to remove.
"""

from __future__ import annotations

import ast
import importlib
import json
import pkgutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic.fields import FieldInfo

import polyswarm_modules

MODULE_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = MODULE_ROOT / "main.py"
DESCRIPTOR_PREFIXES = ("action_", "trigger_", "connector_")
MODEL_SUFFIXES = ("Arguments", "Configuration")

_UNSET = object()


def _registration_table() -> dict[str, str]:
    """Map a descriptor's docker_parameters to the class name main.py registers it as.

    Parsed with ast rather than imported, since the registration calls live
    under `if __name__ == "__main__":` and never run on a plain import.
    """
    tree = ast.parse(MAIN_PY.read_text())
    table: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "register"):
            continue
        if len(node.args) != 2:
            continue
        cls_arg, key_arg = node.args
        if isinstance(cls_arg, ast.Name) and isinstance(key_arg, ast.Constant):
            table[str(key_arg.value)] = cls_arg.id
    return table


def _submodules_by_defined_class() -> dict[str, Any]:
    """Map every class name defined (not imported) in a polyswarm_modules submodule to that submodule."""
    owners: dict[str, Any] = {}
    for info in pkgutil.iter_modules(polyswarm_modules.__path__, polyswarm_modules.__name__ + "."):
        short_name = info.name.rsplit(".", 1)[-1]
        if not short_name.startswith(DESCRIPTOR_PREFIXES):
            continue
        submodule = importlib.import_module(info.name)
        for attr_name, obj in vars(submodule).items():
            if isinstance(obj, type) and getattr(obj, "__module__", None) == submodule.__name__:
                owners[attr_name] = submodule
    return owners


def _local_models(submodule: Any) -> list[type[BaseModel]]:
    """Pydantic models defined locally in submodule, not imported into it."""
    return [
        obj
        for obj in vars(submodule).values()
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == submodule.__name__
    ]


def _arguments_model(submodule: Any, descriptor_name: str) -> type[BaseModel]:
    candidates = [m for m in _local_models(submodule) if m.__name__.endswith(MODEL_SUFFIXES)]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        pytest.fail(
            f"{descriptor_name}: no local model in {submodule.__name__} ends in "
            f"{MODEL_SUFFIXES}, so no arguments model could be found for it."
        )
    names = ", ".join(m.__name__ for m in candidates)
    pytest.fail(
        f"{descriptor_name}: {submodule.__name__} defines more than one candidate "
        f"arguments model ({names}); the descriptor drift test cannot tell which one to check."
    )


def _discover_cases() -> list[tuple[str, dict[str, Any], type[BaseModel]]]:
    """Return (descriptor filename, arguments schema, model) for every descriptor with arguments."""
    table = _registration_table()
    owners = _submodules_by_defined_class()
    cases: list[tuple[str, dict[str, Any], type[BaseModel]]] = []

    for path in sorted(MODULE_ROOT.glob("*.json")):
        if not path.name.startswith(DESCRIPTOR_PREFIXES):
            continue
        descriptor = json.loads(path.read_text())
        arguments = descriptor.get("arguments")
        if not arguments or "properties" not in arguments:
            continue

        docker_parameters = descriptor.get("docker_parameters")
        class_name = table.get(docker_parameters)
        if class_name is None:
            pytest.fail(
                f"{path.name}: docker_parameters {docker_parameters!r} is not registered "
                f"by any module.register(...) call in main.py."
            )
            continue

        submodule = owners.get(class_name)
        if submodule is None:
            pytest.fail(
                f"{path.name}: main.py registers {class_name!r}, but no polyswarm_modules "
                f"submodule defines a class of that name."
            )
            continue

        model = _arguments_model(submodule, path.name)
        cases.append((path.name, arguments, model))

    return cases


def _model_default(field: FieldInfo) -> Any:
    """The value a field actually defaults to, including through a default_factory."""
    if field.default_factory is not None:
        try:
            return field.default_factory()  # type: ignore[call-arg]
        except TypeError:
            return field.default_factory({})  # type: ignore[call-arg]
    return field.default


def _model_bound(field: FieldInfo, attr: str) -> Any:
    for constraint in field.metadata:
        value = getattr(constraint, attr, None)
        if value is not None:
            return value
    return _UNSET


_CASES = _discover_cases()
_CASE_IDS = [name for name, _, _ in _CASES]


@pytest.mark.parametrize("descriptor_name,arguments,model", _CASES, ids=_CASE_IDS)
def test_descriptor_matches_model(descriptor_name: str, arguments: dict[str, Any], model: type[BaseModel]) -> None:
    """A descriptor promising a value the model refuses is a silent rejection for the customer."""
    properties: dict[str, Any] = arguments.get("properties", {})
    fields = model.model_fields

    for name, declared in properties.items():
        assert name in fields, (
            f"{descriptor_name}: {name!r} is declared in arguments but has no field on {model.__name__}"
        )

        field = fields[name]

        if "default" in declared:
            assert declared["default"] == _model_default(field), f"{descriptor_name}: {name} default differs"

        bound_checks = (
            ("minimum", "ge"),
            ("exclusiveMinimum", "gt"),
            ("maximum", "le"),
            ("exclusiveMaximum", "lt"),
        )
        for json_key, model_attr in bound_checks:
            if json_key not in declared:
                continue
            bound = _model_bound(field, model_attr)
            assert bound is not _UNSET, (
                f"{descriptor_name}: {name} declares {json_key} but {model.__name__} has no {model_attr} bound"
            )
            assert declared[json_key] == bound, f"{descriptor_name}: {name} {json_key} differs"

    for name in fields:
        assert name in properties, f"{descriptor_name}: {model.__name__}.{name} has no matching property in arguments"
