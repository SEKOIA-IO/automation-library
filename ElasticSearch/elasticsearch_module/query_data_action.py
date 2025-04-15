from typing import Any

from pydantic.v1 import BaseModel

from elasticsearch_module import ElasticSearchAction


class QueryDataArguments(BaseModel):
    query: str
    drop_null_columns: bool = False


class QueryDataAction(ElasticSearchAction):
    name = "Query data"
    description = "Query data from ElasticSearch"

    def run(self, arguments: QueryDataArguments) -> dict[str, Any]:
        return {"data": self.client.execute_query(arguments.query, arguments.drop_null_columns)}
