import requests
from prometheus_client import CollectorRegistry, Counter

from azure_module.metrics.utils import make_prometheus_exporter


def test_make_prometheus_exporter():
    registry = CollectorRegistry()
    counter = Counter(
        name="counter",
        namespace="namespace",
        labelnames=["label"],
        registry=registry,
        documentation="A simple counter",
    )
    counter.labels(label="label1").inc(42)

    exporter = make_prometheus_exporter(0, registry=registry)
    exporter.start()
    (address, port) = exporter.listening_address

    response = requests.get(f"http://{address}:{port}/metrics")
    exporter.stop()
    assert b'namespace_counter_total{label="label1"} 42.0' in response.content
