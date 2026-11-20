from sekoia_automation.action import Action

from ssh_remote.client import ExecutionResult, SSHExecutionError, SSHRunner

DEFAULT_TIMEOUT = 300
MAX_TIMEOUT = 3600


def parse_timeout(value) -> int:
    """Return the execution timeout in seconds, or raise ValueError if it is not a valid one."""
    if value is None or value == "":
        return DEFAULT_TIMEOUT
    # bool is an int subclass: refuse it rather than reading True as 1 second
    if isinstance(value, bool):
        raise ValueError(f"Invalid timeout {value!r}: expected a number of seconds")
    try:
        timeout = int(value)
    except TypeError, ValueError:
        raise ValueError(f"Invalid timeout {value!r}: expected a number of seconds")
    if not 0 < timeout <= MAX_TIMEOUT:
        raise ValueError(f"Invalid timeout {timeout}: it must be between 1 and {MAX_TIMEOUT} seconds")
    return timeout


class _BaseSSHAction(Action):
    def _runner(self, arguments: dict) -> SSHRunner:
        return SSHRunner(self.module.configuration, host=arguments.get("host") or None)

    def _finish(self, result: ExecutionResult, arguments: dict) -> dict:
        self.log(f"Ran on {result.host}, exit code {result.exit_code}", level="info")
        if arguments.get("fail_on_error", True) and result.exit_code != 0:
            # stderr stays out of the error message, which is logged: it may hold secrets echoed by the
            # remote command. It is still available in the results.
            self.error(f"Remote execution on {result.host} exited with code {result.exit_code}")
        return result.to_dict()

    def _execute(self, arguments: dict, command: str, stdin_data: str | None = None) -> dict | None:
        try:
            timeout = parse_timeout(arguments.get("timeout"))
        except ValueError as exc:
            self.error(str(exc))
            return None
        try:
            result = self._runner(arguments).run(command, stdin_data=stdin_data, timeout=timeout)
        except SSHExecutionError as exc:
            self.error(str(exc))
            return None
        return self._finish(result, arguments)


class RunSSHCommand(_BaseSSHAction):
    def run(self, arguments: dict) -> dict | None:
        command = (arguments.get("command") or "").strip()
        if not command:
            self.error("The command is empty")
            return None
        return self._execute(arguments, command)


class RunSSHScript(_BaseSSHAction):
    def run(self, arguments: dict) -> dict | None:
        script = arguments.get("script") or ""
        if not script.strip():
            self.error("The script is empty")
            return None
        # Normalise Windows line endings, which break bash
        script = script.replace("\r\n", "\n")
        if not script.endswith("\n"):
            script += "\n"
        interpreter = arguments.get("interpreter") or "/bin/bash -s"
        return self._execute(arguments, interpreter, stdin_data=script)
