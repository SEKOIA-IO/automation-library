import argparse
import json
import subprocess
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


def find_changed_json_files() -> list[str]:
    """
    Find all changed json files in the repository.

    Returns:
        list[str]:
    """
    diff = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
        capture_output=True
    )

    return [
        changed_file.decode()
        for changed_file in diff.stdout.splitlines()
        if changed_file.decode().endswith(".json")
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
    """
    parser = argparse.ArgumentParser(description="Linter")
    parser.add_argument("action", choices=["check", "fix"])
    parser.add_argument(
        "--changes", action="store_true", help="Check/Fix only changed files"
    )
    args = parser.parse_args()

    files = find_changed_json_files() if args.changes else load_all_json_files(".")

    format_json_files(files, check_only=args.action == "check")


if __name__ == "__main__":
    main()
