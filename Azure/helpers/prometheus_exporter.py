import threading
from http.server import HTTPServer
from typing import Any, Optional

from prometheus_client.exposition import MetricsHandler
from prometheus_client.registry import REGISTRY, CollectorRegistry


class PrometheusExporterThread(threading.Thread):
    """A thread clast that holds http and makes it serve_forever()."""

    def __init__(self, httpd: HTTPServer, *args: Any, **kwargs: Optional[Any]) -> None:
        """
        Initialize PrometheusExporterThread.

        Args:
            httpd: HTTPServer
            *args: Any
            **kwargs: Optional[Any]
        """
        super().__init__(*args, **kwargs)  # type: ignore
        self.httpd = httpd

    @property
    def listening_address(self) -> tuple[str, int]:
        """
        Listening address and port of the server.

        Returns:
            tuple[str, int]:
        """
        return self.httpd.server_address

    def run(self) -> None:
        self.httpd.serve_forever()

    def stop(self) -> None:
        """Stop the server."""
        self.httpd.shutdown()
        self.httpd.server_close()


def make_prometheus_exporter(
    port: int, addr: str = "0.0.0.0", registry: CollectorRegistry = REGISTRY
) -> PrometheusExporterThread:
    """
    Create the stoppable Prometheus HTTP metrics exporter.

    Args:
        port: int
        addr: str
        registry: CollectorRegistry

    Returns:
        PrometheusExporterThread:
    """
    httpd = HTTPServer((addr, port), MetricsHandler.factory(registry))
    exporter = PrometheusExporterThread(httpd)
    exporter.daemon = True

    return exporter
