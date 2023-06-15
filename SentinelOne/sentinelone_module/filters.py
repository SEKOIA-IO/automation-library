from management.common.query_filter import QueryFilter
from pydantic import BaseModel

from sentinelone_module.helpers import camelize


class BaseFilters(BaseModel):
    class Config:
        query_filter_class: QueryFilter

    def to_query_filter(self) -> QueryFilter:
        assert getattr(self, "Config", None) and getattr(
            self.Config, "query_filter_class", None
        ), "Please define a SentinelOne `query_filter_class` in the configuration of the model"
        query_filter = self.Config.query_filter_class()

        for field_name in self.__fields__.keys():
            if value := getattr(self, field_name):
                query_filter.apply(camelize(field_name), value)

        return query_filter
