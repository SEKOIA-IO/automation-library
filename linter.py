import argparse
import json
import subprocess
import sys
import glob


def load_all_json_files(base_path: str) -> list[str]:
    """
    Load all json files in the repository.

    Args:
        base_path: str

    Returns:
        list[str]:
    """
    return list(glob.glob(base_path + '/**/*.json', recursive=True))


def find_changed_json_files(base: str) -> list[str]:
    """
    Find the json files changed since the merge base with `base`, deleted files excluded.

    Args:
        base: str

    Returns:
        list[str]:
    """
    diff = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=d", "{0}...HEAD".format(base)],
        capture_output=True,
        text=True,
    )
    if diff.returncode != 0:
        sys.exit("git diff against {0} failed: {1}".format(base, diff.stderr.strip()))

    return [
        changed_file
        for changed_file in diff.stdout.splitlines()
        if changed_file.endswith(".json")
    ]


def format_json_file(file_path: str, check_only: bool = True) -> bool:
    """
    Run format on a single file.

    Args:
        file_path: str
        check_only: bool
    """
    with open(file_path, "rt") as file:
        file_content = file.read()

    expected_content = json.dumps(json.loads(file_content), indent=2)

    if file_content != expected_content and check_only:
        print("File {0} is not formatted correctly".format(file_path))

        return False

    if file_content != expected_content:
        print("File {0} is not formatted correctly. Fixing it...".format(file_path))
        with open(file_path, "wt") as file:
            file.write(expected_content)

    return True


def format_json_files(file_paths: list[str], check_only: bool = True):
    """
    Run json format on the list of files.

    Args:
        file_paths: list[str]
        check_only: bool
    """
    invalid_files = [
        file_path
        for file_path in file_paths
        if not format_json_file(file_path, check_only)
    ]

    if invalid_files:
        raise ValueError(
            "Some files are not formatted correctly. Please fix them manually: \n{0}".format(
                "\n".join(invalid_files)
            )
        )


def main():
    """
    Lint all json files in the repository using json.dumps.

    Example of usage:

    1. Check all json files in the repository: python linter.py check
    2. Fix all json files in the repository: python linter.py fix
    3. Check only changed json files: python linter.py check --changes
    4. Fix only changed json files: python linter.py fix --changes
    5. Compare with another branch: python linter.py check --changes --base origin/main
    """
    parser = argparse.ArgumentParser(description="Linter")
    parser.add_argument("action", choices=["check", "fix"])
    parser.add_argument(
        "--changes", action="store_true", help="Check/Fix only changed files"
    )
    parser.add_argument(
        "--base", default="origin/develop", help="Branch to compare with when using --changes"
    )
    args = parser.parse_args()

    if args.changes:
        files = find_changed_json_files(args.base)
        print("{0} changed json file(s) to check:".format(len(files)))
        for file_path in files:
            print("  {0}".format(file_path))
    else:
        files = load_all_json_files(".")

    format_json_files(files, check_only=args.action == "check")


if __name__ == "__main__":
    main()
