from typing import ClassVar

from management.common.query_filter import QueryFilter
from pydantic import BaseModel

from sentinelone_module.helpers import camelize


class BaseFilters(BaseModel):
    # Declared by each subclass; a ClassVar so Pydantic does not treat it as a model field
    query_filter_class: ClassVar[type[QueryFilter] | None] = None

    def to_query_filter(self) -> QueryFilter:
        if self.query_filter_class is None:
            raise TypeError("Please define a SentinelOne `query_filter_class` on the model")

        query_filter = self.query_filter_class()

        for field_name, value in self:
            if value:
                query_filter.apply(camelize(field_name), value)

        return query_filter
