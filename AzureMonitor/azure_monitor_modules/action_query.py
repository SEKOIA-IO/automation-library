from datetime import datetime
from typing import Any

import orjson
import pandas as pd
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
        60,
        description="The maximum time, in seconds, the query should be processed in",
    )


class AzureMonitorQueryAction(AzureMonitorBaseAction):
    module: AzureMonitorModule

    def run(self, arguments: AzureMonitorQueryArguments) -> Any:
        timespan = (
            (arguments.from_date, arguments.to_date)
            if arguments.from_date is not None and arguments.to_date is not None
            else None
        )

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
            df = pd.DataFrame(data=table.rows, columns=table.columns)

            # this is a hack to avoid converting datetime columns manually
            pure_records = orjson.loads(df.to_json(orient="records"))
            result.append(pure_records)

        return result
