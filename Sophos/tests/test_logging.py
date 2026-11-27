import logging

from sophos_module.logging import get_logger


def test_get_logger(caplog):
    caplog.set_level(logging.INFO)
    logger = get_logger("sophos-test")

    logger.info("Sophos logging test", status_code=200)
    logger.debug("hidden at the default level")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.name == "sophos-test"
    assert "Sophos logging test" in record.getMessage()
    assert "status_code=200" in record.getMessage()
    assert "level=info" in record.getMessage()
