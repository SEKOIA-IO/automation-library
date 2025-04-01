from datetime import datetime, timezone
from typing import Any

from azure.core.exceptions import HttpResponseError
from azure.monitor.query import LogsQueryStatus
from pydantic.v1 import BaseModel, Field

from . import AzureMonitorModule
from .action_base import AzureMonitorBaseAction


class AzureMonitorQueryArguments(BaseModel):
    workspace_id: str = Field(..., description="Workspace ID")
    query: str = Field(..., description="Query")
    from_date: datetime | None = Field(None, description="Get data after this timestamp")
    to_date: datetime | None = Field(None, description="Get data before or at this timestamp")
    timeout: int = Field(
        300,
        description="The maximum time, in seconds, the query should be processed in",
    )


class AzureMonitorQueryAction(AzureMonitorBaseAction):
    module: AzureMonitorModule

    @staticmethod
    def format_date(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def run(self, arguments: AzureMonitorQueryArguments) -> Any:
        timespan = (
            (arguments.from_date, arguments.to_date)
            if arguments.from_date is not None and arguments.to_date is not None
            else None
        )
        if (arguments.from_date is None) != (arguments.to_date is None):
            self.log(
                message="Date filter won't affect current query. You should either set both start date and end "
                "date or none of them.",
                level="warning",
            )

        try:
            response = self.client.query_workspace(
                workspace_id=arguments.workspace_id,
                query=arguments.query,
                timespan=timespan,
                server_timeout=arguments.timeout,
            )

            if response.status == LogsQueryStatus.SUCCESS:
                data = response.tables

            else:
                # LogsQueryPartialResult - handle error here
                error = response.partial_error
                data = response.partial_data
                self.log(error, level="error")

            result = []
            for table in data:
                table_records = [
                    {
                        col: self.format_date(value) if isinstance(value, datetime) else value
                        for col, value in zip(table.columns, row)
                    }
                    for row in table.rows
                ]
                result.append({"name": table.name, "records": table_records})

            return {"data": result}

        except HttpResponseError as err:
            self.log(message=str(err), level="error")
