from pathlib import Path

from sekoia_automation.action import Action

from polyswarm_modules import PolyswarmModule


class PolyswarmAction(Action):
    """Base class for PolySwarm actions.

    Declares the module type so the configuration is accessed as a model,
    which is what the SDK builds from the module configuration.
    """

    module: PolyswarmModule

    @staticmethod
    def is_complete(result: object) -> bool:
        """True when a scan carries a verdict that can be reported.

        A result whose assertion window is still open has no verdict yet: the
        engines have not all answered, so its counts are zero and its polyscore
        is empty. Reporting that as a finished scan tells a playbook the sample
        is clean when nobody has looked at it.
        """
        return bool(getattr(result, "window_closed", False)) and not getattr(result, "failed", False)

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
        base = data_path.resolve() if hasattr(data_path, "resolve") else data_path
        joined = base / candidate
        resolved = joined.resolve() if hasattr(joined, "resolve") else joined
        if base not in resolved.parents:
            self.error("File path resolves outside the run data directory")
            return None
        if not resolved.is_file():
            self.error("File was not found in the run data directory")
            return None

        return resolved
