import os
from typing import Any

import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper("iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.LogfmtRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(int(os.environ.get("LOG_LEVEL", 20))),
)


def get_logger(*args: Any) -> Any:
    return structlog.get_logger(*args)
