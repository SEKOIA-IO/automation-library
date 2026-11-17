from sekoia_automation.action import Action

from ssh_remote.client import ExecutionResult, SSHExecutionError, SSHRunner


class _BaseSSHAction(Action):
    def _runner(self, arguments: dict) -> SSHRunner:
        return SSHRunner(self.module.configuration, host=arguments.get("host") or None)

    def _finish(self, result: ExecutionResult, arguments: dict) -> dict:
        self.log(f"Ran on {result.host}, exit code {result.exit_code}", level="info")
        if arguments.get("fail_on_error", True) and result.exit_code != 0:
            self.error(
                f"Remote execution on {result.host} exited with code {result.exit_code}: {result.stderr[-2000:]}"
            )
        return result.to_dict()

    def _execute(self, arguments: dict, command: str, stdin_data: str | None = None) -> dict | None:
        try:
            result = self._runner(arguments).run(
                command, stdin_data=stdin_data, timeout=int(arguments.get("timeout") or 300)
            )
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
