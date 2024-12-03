import enum

from management.mgmtsdk_v2.exceptions import raise_from_response
from pydantic import BaseModel
from tenacity import Retrying, stop_after_delay, wait_exponential

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.exceptions import (
    RemoteScriptExecutionCanceledError,
    RemoteScriptExecutionError,
    RemoteScriptExecutionFailedError,
    RemoteScriptExecutionTimeoutError,
)
from sentinelone_module.rso import RemoteScriptsFilters


class ExecuteRemoteScriptSettings(BaseModel):
    inputParams: str | None
    password: str | None
    outputDirectory: str | None
    scriptRuntimeTimeoutSeconds: int | None


class OutputDestination(str, enum.Enum):
    sentinel_cloud = "SentinelCloud"
    local = "Local"
    none = "None"


class ExecuteRemoteScriptArguments(BaseModel):
    filters: RemoteScriptsFilters | None
    settings: ExecuteRemoteScriptSettings
    script_id: str
    output_destination: OutputDestination
    task_description: str
    timeout: int

    def get_args(self):
        args = self.settings.dict(exclude_unset=True, exclude_none=True)
        args.update(
            {
                "scriptId": self.script_id,
                "outputDestination": self.output_destination,
                "taskDescription": self.task_description,
            }
        )

        # if not defined by the user, default to timeout
        if "scriptRuntimeTimeoutSeconds" not in args:
            args["scriptRuntimeTimeoutSeconds"] = self.timeout

        return args

    def get_query_filters(self):
        if self.filters is None:
            return None

        return self.filters.to_query_filter()


class ExecuteRemoteScriptResultFile(BaseModel):
    download_url: str | None


class ExecuteRemoteScriptResult(BaseModel):
    status: str
    status_reason: str
    result_file: ExecuteRemoteScriptResultFile | None


class ExecuteRemoteScriptAction(SentinelOneAction):
    name = "Execute Remote Script"
    description = "Execute a remote script and get the result"
    results_model = ExecuteRemoteScriptResult

    def _wait_for_completion(self, task_id: str, timeout: int) -> dict[str, str]:
        for attempt in Retrying(
            stop=stop_after_delay(timeout),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        ):
            with attempt:
                result = self.client.remote_scripts.status(parentTaskId=task_id)
                execution_state: dict[str, str] = next(
                    execution for execution in result.json["data"] if execution["parentTaskId"] == task_id
                )

                if execution_state["status"].lower() == "completed":
                    return execution_state
                elif execution_state["status"].lower() == "canceled":
                    raise RemoteScriptExecutionCanceledError(execution_state["detailedStatus"])
                elif execution_state["status"].lower() == "failed":
                    raise RemoteScriptExecutionFailedError(execution_state["detailedStatus"])

        raise RemoteScriptExecutionTimeoutError(timeout)

    def run(self, arguments: ExecuteRemoteScriptArguments):
        result = self.client.remote_scripts.execute(arguments.get_args(), query_filter=arguments.get_query_filters())

        try:
            status = self._wait_for_completion(result.data["parentTaskId"], arguments.timeout)

            params = {
                "agentId": status["agentId"],
                "siteId": status["siteId"],
                "signature": status["scriptResultsSignature"],
                "signatureType": "SHA256",
            }
            output = self.client.client.get(endpoint="remote-scripts/fetch-file", params=params)
            if output.status_code != 200:
                self.log("Failed to fetch download links", level="warning")
                raise_from_response(output)

            return {
                "status": "succeed",
                "status_reason": "The remote script was successfully executed",
                "result_file": {"download_url": output.json["data"].get("downloadUrl")},
            }
        except RemoteScriptExecutionError as error:
            return {
                "status": error.status,
                "status_reason": str(error),
                "result_file": None,
            }
