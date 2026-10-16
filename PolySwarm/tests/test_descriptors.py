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
import re
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

        # The reverse direction: a bound the model enforces must also be declared, otherwise the
        # catalogue lets the user type a value the action then rejects.
        for json_key, model_attr in bound_checks:
            bound = _model_bound(field, model_attr)
            if bound is not _UNSET:
                assert json_key in declared, (
                    f"{descriptor_name}: {name} has {model_attr}={bound} on {model.__name__} "
                    f"but the descriptor declares no {json_key}"
                )

    for name in fields:
        assert name in properties, f"{descriptor_name}: {model.__name__}.{name} has no matching property in arguments"


# ---------------------------------------------------------------------------
# Results schema: every declared result field must agree with the response model
# ---------------------------------------------------------------------------

import types  # noqa: E402
import typing  # noqa: E402

_SCALAR_TYPES = {bool: "boolean", int: "integer", float: "number", str: "string"}


def _json_types(annotation: Any) -> set[str] | None:
    """JSON types a pydantic annotation allows, or None when it accepts anything (Any / unparameterised object)."""
    if annotation is Any or annotation is object:
        return None
    if annotation is type(None):
        return {"null"}
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        collected: set[str] = set()
        for arm in typing.get_args(annotation):
            arm_types = _json_types(arm)
            if arm_types is None:
                return None
            collected |= arm_types
        return collected
    if annotation in _SCALAR_TYPES:
        return {_SCALAR_TYPES[annotation]}
    if origin in (list, set, tuple, frozenset) or annotation in (list, set, tuple, frozenset):
        return {"array"}
    if origin is dict or annotation is dict:
        return {"object"}
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {"object"}
    pytest.fail(f"unsupported annotation in a response model: {annotation!r}")


def _item_annotation(annotation: Any) -> Any:
    """The element annotation of a list, looking through Optional."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        for arm in typing.get_args(annotation):
            if arm is not type(None) and _item_annotation(arm) is not None:
                return _item_annotation(arm)
        return None
    if origin in (list, set, tuple, frozenset):
        args = typing.get_args(annotation)
        return args[0] if args else Any
    return None


def _object_model(annotation: Any) -> type[BaseModel] | None:
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        for arm in typing.get_args(annotation):
            found = _object_model(arm)
            if found is not None:
                return found
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _declared_types(declared: dict[str, Any]) -> set[str]:
    raw = declared.get("type")
    if raw is None:
        return set()
    return {raw} if isinstance(raw, str) else set(raw)


def _check_schema(path: str, schema: dict[str, Any], annotation: Any, model_name: str, problems: list[str]) -> None:
    allowed = _json_types(annotation)
    declared = _declared_types(schema)
    if allowed is not None and declared != allowed:
        problems.append(
            f"{path}: descriptor declares type {sorted(declared)} but {model_name} allows {sorted(allowed)}"
        )

    nested = _object_model(annotation)
    if nested is not None and "properties" in schema:
        _check_properties(path, schema["properties"], nested, problems)

    item_annotation = _item_annotation(annotation)
    if item_annotation is not None and "items" in schema:
        _check_schema(f"{path}[]", schema["items"], item_annotation, model_name, problems)


def _check_properties(path: str, properties: dict[str, Any], model: type[BaseModel], problems: list[str]) -> None:
    for name, schema in properties.items():
        field_path = f"{path}.{name}" if path else name
        if name not in model.model_fields:
            problems.append(f"{field_path}: declared in results but {model.__name__} has no such field")
            continue
        _check_schema(field_path, schema, model.model_fields[name].annotation, model.__name__, problems)
    for name in model.model_fields:
        if name not in properties:
            problems.append(f"{path + '.' if path else ''}{name}: {model.__name__} field is missing from results")


def _discover_result_cases() -> list[tuple[str, dict[str, Any], type[BaseModel]]]:
    table = _registration_table()
    owners = _submodules_by_defined_class()
    cases: list[tuple[str, dict[str, Any], type[BaseModel]]] = []
    for path in sorted(MODULE_ROOT.glob("*.json")):
        if not path.name.startswith(DESCRIPTOR_PREFIXES):
            continue
        results = json.loads(path.read_text()).get("results")
        if not results or "properties" not in results:
            continue
        class_name = table.get(json.loads(path.read_text()).get("docker_parameters"))
        submodule = owners.get(class_name) if class_name else None
        if submodule is None:
            pytest.fail(f"{path.name}: no registered class found for its docker_parameters")
            continue
        candidates = [m for m in _local_models(submodule) if m.__name__.endswith("Response")]
        if len(candidates) != 1:
            # Triggers and connectors declare their payload differently and are covered by their own tests.
            continue
        cases.append((path.name, results, candidates[0]))
    return cases


_RESULT_CASES = _discover_result_cases()


def test_result_cases_cover_every_action() -> None:
    """A new action must not slip past the results check by lacking a Response model."""
    covered = {name for name, _, _ in _RESULT_CASES}
    expected = {p.name for p in MODULE_ROOT.glob("action_*.json")}
    assert covered == expected, f"actions without a checked results schema: {sorted(expected - covered)}"


@pytest.mark.parametrize("descriptor_name,results,model", _RESULT_CASES, ids=[n for n, _, _ in _RESULT_CASES])
def test_results_match_response_model(descriptor_name: str, results: dict[str, Any], model: type[BaseModel]) -> None:
    """A result field typed more narrowly than its model misleads the playbook author.

    A field declared number where the model allows None is the case that got
    through last round.
    """
    problems: list[str] = []
    _check_properties("", results["properties"], model, problems)
    assert not problems, f"{descriptor_name}:\n" + "\n".join(problems)


def test_every_action_has_a_unique_snake_case_slug() -> None:
    """The slug is what makes an action callable by name from a notebook, and it must never change."""
    slugs: dict[str, str] = {}
    for path in sorted(MODULE_ROOT.glob("action_*.json")):
        slug = json.loads(path.read_text()).get("slug")
        assert slug, f"{path.name}: no slug"
        assert re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", slug), f"{path.name}: slug {slug!r} is not snake_case"
        assert slug not in slugs, f"{path.name}: slug {slug!r} is already used by {slugs[slug]}"
        slugs[slug] = path.name
    assert slugs.get("scan_domain") == "action_scandomain.json", "scan_domain is published and must not be renamed"


def test_descriptors_use_the_linter_format() -> None:
    """The Sekoia linter wants exactly json.dumps(..., indent=2) with no trailing newline."""
    bad = [
        path.name
        for path in sorted(MODULE_ROOT.glob("*.json"))
        if path.read_text() != json.dumps(json.loads(path.read_text()), indent=2)
    ]
    assert not bad, f"not in linter format: {bad}"
