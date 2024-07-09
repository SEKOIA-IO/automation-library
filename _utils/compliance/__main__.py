import argparse
import json
import subprocess
from collections import defaultdict
from functools import partial
from pathlib import Path

from validators import MODULES_PATH, ModuleValidator
from validators.models import CheckError


def check_module(module_path: str | Path, args: argparse.Namespace):
    if isinstance(module_path, str):
        module_path = Path(module_path)

    m = ModuleValidator(path=module_path, args=args)
    m.validate()

    return m


def format_errors(mod_val: ModuleValidator, ignored_paths: set[Path]) -> str:
    errors = mod_val.result.errors
    module_name = mod_val.path.name
    return "\n".join(
        "%s:%s:%s" % (module_name, error.filepath.name, error.error)
        for error in errors
        if error.filepath not in ignored_paths
    )


def find_modules(root_path: Path) -> list[Path]:
    result = []

    for path in root_path.iterdir():
        if (
            path.is_dir()
            and not path.name.startswith("_")
            and not path.name.startswith(".")
            and path.name not in ("docs",)
        ):
            result.append(path)

    return result


def find_changed_modules(root_path: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"], capture_output=True
    )
    changed_modules = set()
    for changed_file in result.stdout.splitlines():
        changed_file = changed_file.decode()
        module_folder = changed_file.split("/")[0]
        module_path = root_path / module_folder
        if "_utils" in str(module_path):
            print("Compliance code folder is changed - check all modules")
            return sorted(find_modules(root_path))

        if (
            module_path.is_dir()
            and not module_path.name.startswith("_")
            and not module_path.name.startswith(".")
            and module_path.name not in ("docs",)
        ):
            changed_modules.add(module_path)

    return sorted(list(changed_modules))


def fix_set_uuid(file_path: Path, uuid: str) -> None:
    with open(file_path, "rt") as file:
        manifest = json.load(file)

    manifest["uuid"] = uuid

    with open(file_path, "wt") as file:
        json.dump(manifest, file, indent=2)


def check_uniqueness(items, error_msg: str):
    for k, v in items.items():
        if len(v) > 1:
            for file_name, val in v:
                path = val.result.options["path"] / file_name

                # We don't add fix call (e.g. generating new UUID) here, because it would create
                # a lot of error-prone corner cases
                val.result.errors.append(
                    CheckError(
                        filepath=path,
                        error=error_msg,
                    )
                )


def check_docker_params(validators: list[ModuleValidator]):
    for validator in validators:
        actions_docker_params = defaultdict(list)
        triggers_docker_params = defaultdict(list)
        connectors_docker_params = defaultdict(list)

        module_path = validator.result.options["path"]
        docker_parameters = validator.result.options.get("docker_parameters", {})

        suffix_to_docker = defaultdict(dict)
        for filename, docker in docker_parameters.items():
            if filename.startswith("action_"):
                actions_docker_params[docker].append((filename, validator))
                suffix_to_docker[filename.lstrip("action_")]["action"] = docker

            elif filename.startswith("trigger_"):
                triggers_docker_params[docker].append((filename, validator))
                suffix_to_docker[filename.lstrip("trigger_")]["trigger"] = docker

            elif filename.startswith("connector_"):
                connectors_docker_params[docker].append((filename, validator))
                suffix_to_docker[filename.lstrip("connector_")]["connector"] = docker

        for suffix, data in suffix_to_docker.items():
            # ignore cases where we have only either `trigger_` or `connector_` files
            if "connector" not in data or "trigger" not in data:
                continue

            if data["connector"] != data["trigger"]:
                filename_to_fix = "connector_%s" % suffix
                filepath = module_path / filename_to_fix
                validator.result.errors.append(
                    CheckError(
                        filepath=filepath,
                        error=f"`docker_parameters` is not consistent with trigger_%s"
                        % suffix,
                    )
                )
                # We don't want to check these further
                del triggers_docker_params[data["trigger"]]
                del connectors_docker_params[data["connector"]]

        check_uniqueness(
            actions_docker_params, error_msg="`docker_parameters` is not unique"
        )
        check_uniqueness(
            triggers_docker_params, error_msg="`docker_parameters` is not unique"
        )
        check_uniqueness(
            connectors_docker_params, error_msg="`docker_parameters` is not unique"
        )


def check_uuids_and_slugs(validators: list[ModuleValidator]):
    manifest_uuids = defaultdict(list)
    manifest_slugs = defaultdict(list)
    actions_uuids = defaultdict(list)
    triggers_uuids = defaultdict(list)
    connectors_uuids = defaultdict(list)

    for validator in validators:
        module_path = validator.result.options["path"]

        module_slug = validator.result.options.get("module_slug")
        if module_slug:
            manifest_slugs[module_slug].append(("manifest.json", validator))

        uuids = validator.result.options.get("uuid_to_check", {})

        suffix_to_uuid = defaultdict(dict)
        for filename, uuid in uuids.items():
            if filename == "manifest.json":
                manifest_uuids[uuid].append((filename, validator))

            elif filename.startswith("action_"):
                actions_uuids[uuid].append((filename, validator))

            elif filename.startswith("trigger_"):
                triggers_uuids[uuid].append((filename, validator))
                suffix_to_uuid[filename.lstrip("trigger_")]["trigger"] = uuid

            elif filename.startswith("connector_"):
                connectors_uuids[uuid].append((filename, validator))
                suffix_to_uuid[filename.lstrip("connector_")]["connector"] = uuid

        for suffix, data in suffix_to_uuid.items():
            # ignore cases where we have only either `trigger_` or `connector_` files
            if "connector" not in data or "trigger" not in data:
                continue

            if data["connector"] != data["trigger"]:
                filename_to_fix = "connector_%s" % suffix
                filepath = module_path / filename_to_fix
                validator.result.errors.append(
                    CheckError(
                        filepath=filepath,
                        error=f"UUID is not consistent with trigger_%s" % suffix,
                        fix_label="Set the same UUID for trigger_%s and connector_%s"
                        % (suffix, suffix),
                        fix=partial(
                            fix_set_uuid, file_path=filepath, uuid=data["trigger"]
                        ),
                    )
                )
                # We don't want to check these further
                del triggers_uuids[data["trigger"]]
                del connectors_uuids[data["connector"]]

    # check UUIDs from each group separately
    check_uniqueness(manifest_slugs, error_msg="slug is not unique")
    check_uniqueness(manifest_uuids, error_msg="UUID is not unique")
    check_uniqueness(actions_uuids, error_msg="UUID is not unique")
    check_uniqueness(connectors_uuids, error_msg="UUID is not unique")
    check_uniqueness(triggers_uuids, error_msg="UUID is not unique")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check modules")
    parser.add_argument("action", choices=["check", "fix"])
    parser.add_argument(
        "--changes", action="store_true", help="Check/fix only modified modules"
    )
    parser.add_argument(
        "--module", action="append", default=[], help="Check/fix specific modules"
    )

    # get and parse .complianceignore
    compliance_ignore_path = Path(MODULES_PATH / ".complianceignore")
    paths_to_ignore = []
    if compliance_ignore_path.exists():
        with open(compliance_ignore_path, "rt") as f:
            paths_to_ignore = {
                MODULES_PATH / path
                for path in f.read().split("\n")
                if not path.startswith("#") and len(path) > 0
            }

    args = parser.parse_args()

    all_modules = find_modules(MODULES_PATH)

    if args.changes:
        modules = find_changed_modules(MODULES_PATH)

    elif args.module:
        modules = [MODULES_PATH / module_name for module_name in args.module]

    else:
        # check all modules by default
        modules = all_modules

    print(f"🔎 {len(modules)} module(s) found")

    all_validators = []
    selected_validators = []

    errors_to_fix = []
    has_any_errors = False
    for module in all_modules:
        r = check_module(module, args)
        all_validators.append(r)

        # We have to check all the modules, but show results only for the selected ones
        if module in modules:
            selected_validators.append(r)

    check_uuids_and_slugs(all_validators)
    check_docker_params(all_validators)

    for r in selected_validators:
        if r.result.errors:
            for item in r.result.errors:
                if item.filepath in paths_to_ignore:
                    continue

                has_any_errors = True
                if item.fix is not None:
                    errors_to_fix.append(item)

    for res in sorted(selected_validators, key=lambda x: x.path):
        if len(res.result.errors) > 0:
            fmt = format_errors(res, ignored_paths=paths_to_ignore)
            if fmt:
                print(fmt)

    if args.action == "check":
        if len(errors_to_fix) > 0:
            print()
            print("🛠 Available automatic fixes (run with `fix` command):")
            for error in errors_to_fix:
                print(
                    f"FIX {error.filepath.relative_to(MODULES_PATH)}:{error.fix_label}"
                )

    elif args.action == "fix":
        if len(errors_to_fix) == 0:
            print("There is nothing we can fix automatically")
            print()
            print("Fixing...")
            for error in errors_to_fix:
                print(
                    f"FIX {error.filepath.relative_to(MODULES_PATH)}:{error.fix_label}"
                )
                error.fix()

    if has_any_errors:
        print("❌  Found errors")
        exit(1)

    else:
        print("✅  No errors found!")
