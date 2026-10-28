import tomllib

import pytest

from update_module_dependencies import (
    Dependency,
    declaration_count,
    invalid_name,
    migrate_legacy_dev_dependencies,
    bump_manifest_version,
    parse_poetry_outdated,
    parse_uv_outdated,
    poetry_dependencies,
    uv_dependencies,
    uv_requirement,
)

UV_PYPROJECT = """
[project]
dependencies = [
    "orjson>=3.10.7,<4",
    "requests[socks]>=2.0,<3; python_version >= '3.10'",
    "pinned==1.0.0",
    "loose",
]

[dependency-groups]
dev = ["pytest>=7.0", {include-group = "lint"}]
lint = ["ruff>=0.14"]
"""

POETRY_PYPROJECT = """
[tool.poetry.dependencies]
python = ">=3.10,<3.12"
orjson = "^3.10.16"
pydantic = { version = "^2.10", extras = ["email"] }
local = { path = "../local" }
exact = "1.2.3"

[tool.poetry.group.dev.dependencies]
pytest = "*"
freezegun = "^1.5.1"
"""


def test_uv_dependencies():
    deps = {d.name: d for d in uv_dependencies(tomllib.loads(UV_PYPROJECT))}
    assert set(deps) == {"orjson", "requests", "pinned", "loose", "pytest", "ruff"}
    assert deps["orjson"] == Dependency(None, "orjson", (), None, None)
    assert deps["requests"].extras == ("socks",)
    assert deps["requests"].marker == 'python_version >= "3.10"'
    assert deps["pinned"].skip == "pinned"
    assert deps["loose"].skip.startswith("unbounded")
    assert deps["pytest"].group == "dev"
    assert deps["ruff"].group == "lint"


def test_poetry_dependencies():
    deps = {d.name: d for d in poetry_dependencies(tomllib.loads(POETRY_PYPROJECT))}
    assert set(deps) == {"orjson", "pydantic", "local", "exact", "pytest", "freezegun"}
    assert deps["orjson"].skip is None
    assert deps["pydantic"].extras == ("email",)
    assert deps["pydantic"].skip is None
    assert deps["local"].skip == "complex specification"
    assert deps["exact"].skip == "pinned"
    assert deps["pytest"].skip.startswith("unbounded")
    assert deps["freezegun"].group == "dev"


def test_poetry_pep621_dependencies():
    pyproject = tomllib.loads('[project]\ndependencies = ["orjson>=3", "tomli>=2; python_version < \'3.11\'"]')
    deps = {d.name: d for d in poetry_dependencies(pyproject)}
    assert deps["orjson"].skip is None
    assert deps["tomli"].skip == "has markers"


def test_parse_uv_outdated():
    output = """automation-module-1password v0.0
├── orjson v3.10.18 (latest: v3.13.0)
├── python-dateutil v2.9.0.post0 (latest: v3.0.0)
├── pytest-cov v7.1.0 (group: dev)
└── ruff v0.15.16 (group: lint) (latest: v0.17.3)
"""
    assert parse_uv_outdated(output) == {"orjson": "3.13.0", "python-dateutil": "3.0.0", "ruff": "0.17.3"}


def test_parse_poetry_outdated():
    output = """[
  {"name": "cachetools", "installed_status": "installed", "version": "5.5.2", "latest_version": "7.2.6"},
  {"name": "edgegrid-python", "installed_status": "installed", "version": "2.0.7", "latest_version": "2.0.9"},
  {"name": "Requests_Ratelimiter", "installed_status": "installed", "version": "0.7.0", "latest_version": "0.10.0"}
]"""
    assert parse_poetry_outdated(output) == {
        "cachetools": "7.2.6",
        "edgegrid-python": "2.0.9",
        "requests-ratelimiter": "0.10.0",
    }


def test_uv_requirement():
    dep = Dependency("dev", "requests", ("socks",), 'python_version >= "3.10"', None)
    assert uv_requirement(dep, "2.34.2") == 'requests[socks]>=2.34.2,<3; python_version >= "3.10"'
    assert uv_requirement(dep._replace(extras=(), marker=None), "0.10.0") == "requests>=0.10.0,<1"


def test_bump_manifest_version_keeps_formatting():
    text = '{\n  "name": "Foo",\n  "version": "1.2.3",\n  "slug": "foo"\n}\n'
    assert bump_manifest_version(text) == ('{\n  "name": "Foo",\n  "version": "1.2.4",\n  "slug": "foo"\n}\n', "1.2.4")


def test_bump_manifest_version_ignores_nested_version():
    text = '{\n  "configuration": {"version": "1.2.3"},\n  "version": "1.2.3"\n}\n'
    with pytest.raises(ValueError):
        bump_manifest_version(text)
    text = '{\n  "configuration": {"version": "9.9.9"},\n  "version": "1.2.3"\n}\n'
    new_text, new_version = bump_manifest_version(text)
    assert new_version == "1.2.4"
    assert '"version": "9.9.9"' in new_text


LEGACY_ONLY = """[tool.poetry.dependencies]
python = "^3.11"

[tool.poetry.dev-dependencies]
pytest = "*"
mypy = "^0.991"

[tool.poetry.dev-dependencies.black]
version = "^22.10.0"
extras = ["colorama"]
"""

LEGACY_AND_GROUP = """[tool.poetry.dev-dependencies]
pytest = "*"

[tool.poetry.group.dev.dependencies]
mypy = "^0.991"
"""


def dev_group(text):
    return tomllib.loads(text)["tool"]["poetry"]["group"]["dev"]["dependencies"]


def test_migrate_legacy_dev_dependencies():
    text = migrate_legacy_dev_dependencies(LEGACY_ONLY)
    assert "dev-dependencies" not in tomllib.loads(text)["tool"]["poetry"]
    assert dev_group(text) == {
        "pytest": "*",
        "mypy": "^0.991",
        "black": {"version": "^22.10.0", "extras": ["colorama"]},
    }
    deps = {d.name: d for d in poetry_dependencies(tomllib.loads(text))}
    assert deps["mypy"].group == "dev"
    assert deps["black"].extras == ("colorama",)


def test_migrate_merges_existing_dev_group():
    assert dev_group(migrate_legacy_dev_dependencies(LEGACY_AND_GROUP)) == {"pytest": "*", "mypy": "^0.991"}


def test_migrate_without_legacy_table_is_noop():
    assert migrate_legacy_dev_dependencies(POETRY_PYPROJECT) == POETRY_PYPROJECT


def test_migrate_refuses_package_in_both_tables():
    with pytest.raises(ValueError):
        migrate_legacy_dev_dependencies(LEGACY_AND_GROUP + 'pytest = "^7"\n')


def test_declaration_count():
    pyproject = tomllib.loads(LEGACY_AND_GROUP + '\n[dependency-groups]\ndev = ["Mypy>=2"]\n')
    assert declaration_count(pyproject, "mypy") == 2
    assert declaration_count(pyproject, "pytest") == 1
    assert declaration_count(pyproject, "absent") == 0


def test_invalid_names_are_refused():
    assert not invalid_name(Dependency(None, "orjson", (), None, None))
    assert not invalid_name(Dependency("dev", "ruamel.yaml", (), None, None))
    assert invalid_name(Dependency(None, "--source=x", (), None, None))
    assert invalid_name(Dependency("-v", "orjson", (), None, None))
