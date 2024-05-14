import argparse
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


def run_npx_on_files(files_to_fix: list[str], check_only: bool = True):
    """
    Run prettier on the list of files.

    Args:
        files_to_fix: list[str]
        check_only: bool
    """
    action = "--check" if check_only else "--write"

    result = subprocess.run(
        ["npx", "prettier", action] + files_to_fix,
        capture_output=True
    )

    if result.returncode != 0:
        raise Exception("Prettier failed: \n" + result.stderr.decode())
    else:
        print("Prettier run successfully: \n" + result.stdout.decode())


def main():
    """
    Lint all json files in the repository using prettier.

    Requires prettier to be installed in the repository.
        npm install --save-dev prettier

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

    run_npx_on_files(files, check_only=args.action == "check")


if __name__ == "__main__":
    main()
