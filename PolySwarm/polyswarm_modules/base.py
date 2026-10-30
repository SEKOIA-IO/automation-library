import functools
import hashlib
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sekoia_automation.action import Action

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.verdict import has_verdict

# Every action names its argument model <Action>Arguments. A ValidationError
# from any other model is a payload problem, not a playbook input problem.
ARGUMENTS_MODEL_SUFFIX = "Arguments"


def describe_validation_error(exc: ValidationError) -> str:
    """One analyst readable sentence per rejected argument, naming the field and what was expected.

    The rejected value is left out on purpose: it can be a URL or an indicator
    the analyst did not mean to put in a run log.
    """
    problems: list[str] = []
    for item in exc.errors(include_input=False, include_url=False):
        field = ".".join(str(part) for part in item["loc"]) or "arguments"
        if item["type"] == "missing":
            problems.append(f"'{field}' is required")
        else:
            problems.append(f"'{field}': {item['msg']}")
    return "Invalid action arguments, " + "; ".join(problems) + ". Correct the playbook inputs and run again."


def sha256_handle(handle: Any) -> str:
    """SHA256 of an open file handle, leaving the handle rewound for the client.

    Read in chunks so a large sample is never held in memory whole.
    """
    h = hashlib.sha256()
    for chunk in iter(lambda: handle.read(65536), b""):
        h.update(chunk)
    # The same handle is handed to the client next, which expects to read it from the start.
    handle.seek(0)
    return h.hexdigest()


class PolyswarmAction(Action):
    """Base class for PolySwarm actions.

    Declares the module type so the configuration is accessed as a model,
    which is what the SDK builds from the module configuration.
    """

    module: PolyswarmModule

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Guard each action's run so rejected arguments become an action error.

        Every action builds its own pydantic arguments model at the top of run.
        Wrapping run here covers all of them in one place: a bad value reaches
        the playbook as a readable message instead of a raw traceback.
        """
        super().__init_subclass__(**kwargs)
        run = cls.__dict__.get("run")
        if run is None:
            return

        @functools.wraps(run)
        def guarded(self: PolyswarmAction, arguments: Any) -> Any:
            try:
                return run(self, arguments)
            except ValidationError as exc:
                if not exc.title.endswith(ARGUMENTS_MODEL_SUFFIX):
                    # A response model refusing a payload means the API answered
                    # with something the module did not expect. Reporting that as
                    # a bad argument sends the analyst to the wrong place.
                    raise
                self.error(describe_validation_error(exc))
                return None

        cls.run = guarded  # type: ignore[method-assign,assignment]

    @staticmethod
    def is_complete(result: object) -> bool:
        """True when a result carries a verdict that can be reported.

        Three things keep a result from being reportable, and each one would
        otherwise read as a clean artifact. An assertion window that is still
        open means the engines have not all answered, so counts are zero and the
        polyscore is empty. A failed scan has no verdict by definition. A closed
        window with no malicious or benign answer inside the mask (no engine
        covers this artifact type, or every engine abstained) means nobody
        looked. This method returns False for all three, so a caller can send
        them to its unknown branch instead of "not detected".
        """
        return (
            bool(getattr(result, "window_closed", False))
            and not getattr(result, "failed", False)
            and has_verdict(result)
        )

    def resolve_data_file(self, value: str) -> Path | None:
        """Resolve a file reference from a playbook, confined to the run data directory.

        Sekoia writes the files a playbook hands to a module underneath
        data_path, so a file reference is a name relative to that directory.
        Absolute paths, parent traversal and symlinks that point outside the
        directory are refused. The container also holds the credentials of the
        run itself, and an action that opens whatever path it is given would
        upload them to the configured community.

        Returns None and records an action error when the reference is refused,
        which the caller surfaces to the playbook instead of a result.
        """
        candidate = Path(value)
        if candidate.is_absolute():
            self.error("File must be a path relative to the run data directory")
            return None

        # Do not wrap data_path in Path(): the SDK hands back an S3 backed path
        # when the platform runs that file backend, and wrapping it silently
        # produces a local path that does not exist. Use what the SDK gave us.
        data_path = self.data_path
        if isinstance(data_path, str):
            data_path = Path(data_path)
        try:
            base = data_path.resolve() if hasattr(data_path, "resolve") else data_path
            joined = base / candidate
            resolved = joined.resolve() if hasattr(joined, "resolve") else joined
        except (OSError, ValueError):
            # A name with a NUL byte makes resolve() raise ValueError, and a symlink loop raises OSError.
            self.error("File path could not be resolved in the run data directory")
            return None
        if base not in resolved.parents:
            self.error("File path resolves outside the run data directory")
            return None
        if not resolved.is_file():
            self.error("File was not found in the run data directory")
            return None

        return resolved
