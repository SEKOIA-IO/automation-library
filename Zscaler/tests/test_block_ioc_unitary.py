from zscaler.block_ioc import ZscalerAction
from unittest.mock import MagicMock


def test_get_valid_indicators_from_stix():
    # Mocking necessary dependencies or objects
    stix_objects = [
        {
            "valid_from": "2023-04-03T00:00:00Z",
            "x_ic_observable_types": ["ipv4-addr"],
            "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
            "object_marking_refs": ["marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"],
            "type": "indicator",
            "name": "77.91.78.118",
            "pattern": "[ipv4-addr:value = '77.91.78.118']",
            "revoked": False,
        },
        {
            "valid_from": "2023-04-03T00:00:00Z",
            "x_ic_observable_types": ["domain-name"],
            "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
            "object_marking_refs": ["marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"],
            "type": "indicator",
            "name": "77.91.78.118",
            "pattern": "[domain-name:value = 'example.com']",
            "revoked": True,
        },
    ]

    # Call the method you want to test
    results = ZscalerAction.get_valid_indicators_from_stix(None, stix_objects)
    print(results)
    # Perform assertions based on the expected behavior of the method
    assert "valid" in results
    assert "revoked" in results
    assert "77.91.78.118" in results["valid"]
    assert "example.com" in results["revoked"]
