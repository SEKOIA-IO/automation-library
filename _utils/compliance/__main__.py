import argparse
import subprocess
from pathlib import Path

from validators import MODULES_PATH, ModuleValidator
from validators.models import CheckError, CheckResult


def check_module(module_path: str | Path, args: argparse.Namespace):
    if isinstance(module_path, str):
        module_path = Path(module_path)

    m = ModuleValidator(path=module_path, args=args)
    m.validate()

    return m


def format_errors(mod_val: ModuleValidator) -> str:
    errors = mod_val.result.errors
    module_name = mod_val.path.name
    return "\n".join(
        "%s:%s:%s" % (module_name, error.filepath.name, error.error) for error in errors
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
        changed_modules.add(module_path)

    return sorted(list(changed_modules))


def check_module_uuids_and_slugs(check_module_results: list[CheckResult]):
    # MANIFEST
    module_uuids: dict[str, str] = dict()
    for module_result in check_module_results:
        if (
            len(module_result.errors) == 0
            and "uuid_to_check" in module_result.options
            and "manifest.json" in module_result.options["uuid_to_check"]
            and module_result.options["uuid_to_check"]["manifest.json"] in module_uuids
        ):
            module_result.errors.append(
                CheckError(
                    filepath=module_result.options["manifest_path"],
                    error=f"module have the same uuid ({module_result.options['uuid_to_check']['manifest.json']}) "
                    f"than module {module_uuids[module_result.options['manifest_uuid']]}",
                )
            )

            module_uuids[module_result.options["uuid_to_check"]["manifest.json"]] = (
                module_result.options.get("uuid_to_check", {}).get(
                    "manifest.json", "unknown"
                )
            )

    # @todo also check every action, trigger and connector JSONs?


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check modules")
    parser.add_argument("action", choices=["check", "fix"])
    parser.add_argument(
        "--changes", action="store_true", help="Check/fix only modified modules"
    )
    parser.add_argument(
        "--module", action="append", default=[], help="Check/fix specific modules"
    )

    args = parser.parse_args()

    if args.changes:
        modules = find_changed_modules(MODULES_PATH)

    elif args.module:
        modules = [MODULES_PATH / module_name for module_name in args.module]

    else:
        # check all modules by default
        modules = find_modules(MODULES_PATH)

    all_validators = []
    errors_to_fix = []
    has_any_errors = False
    for module in modules:
        r = check_module(module, args)
        all_validators.append(r)

        if r.result.errors:
            has_any_errors = True
            for item in r.result.errors:
                if item.fix is not None:
                    errors_to_fix.append(item)

    check_module_uuids_and_slugs([item.result for item in all_validators])
    for res in sorted(all_validators, key=lambda x: x.path):
        print(format_errors(res))

    if args.action == "check":
        print()
        print("Available automatic fixes (run with `fix` command):")
        for error in errors_to_fix:
            print(f"FIX {error.filepath.relative_to(MODULES_PATH)}:{error.fix_label}")

        if has_any_errors:
            exit(1)

    elif args.action == "fix":
        print()
        print("Fixing...")
        for error in errors_to_fix:
            print(f"FIX {error.filepath.relative_to(MODULES_PATH)}:{error.fix_label}")
            # @todo call actual function
