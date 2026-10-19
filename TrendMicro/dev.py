"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path
from typing import Any, Literal

from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_email_sec import TrendMicroConnectorConfiguration, TrendMicroEmailSecurityConnector

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
logger = logging.getLogger(__name__)


def dumb_log(
    message: str,
    level: Literal["fatal", "critical", "error", "warning", "info", "debug"] = "info",
    **_kwargs: Any,
) -> None:
    log_level = logging.getLevelName(level.upper())
    logger.log(log_level, message)


def dumb_log_exception(exception: Exception, **kwargs: Any) -> None:
    message = kwargs.get("message", "An exception occurred")
    logger.exception(message, exc_info=exception)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--service_url", type=str, required=True)
    parser.add_argument("--username", type=str, required=True)
    parser.add_argument("--api_key", type=str, required=True)
    parser.add_argument("--intake_key", type=str, required=True)

    args = parser.parse_args()

    class DumbConnectorConfiguration(TrendMicroConnectorConfiguration):
        service_url: str = args.service_url
        username: str = args.username
        api_key: str = args.api_key

        batch_size: int = 2
        frequency: int = 13
        intake_key: str = args.intake_key

        # https://intake.test.sekoia.io or https://intake.sekoia.io
        intake_server: str = "https://intake.sekoia.io"

    connector_conf = DumbConnectorConfiguration()

    module = TrendMicroModule()

    conn = TrendMicroEmailSecurityConnector(module=module, data_path=Path("."))
    conn.configuration = connector_conf

    # Replace logging methods to make them work locally
    setattr(conn, "log", dumb_log)
    setattr(conn, "log_exception", dumb_log_exception)

    conn.run()
