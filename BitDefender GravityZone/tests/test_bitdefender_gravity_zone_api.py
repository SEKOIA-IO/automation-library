from bitdefender.bitdefender_gravity_zone_api import (
    prepare_add_quarantine_file_endpoint,
    prepare_restore_quarantine_file_endpoint,
)


def test_prepare_quarantine_endpoints_methods():
    params = {"endpointId": "abc"}

    add_to_quarantine = prepare_add_quarantine_file_endpoint(params)
    assert add_to_quarantine["api"] == "api/v1.1/jsonrpc/quarantine/computers"
    assert add_to_quarantine["body"]["method"] == "createAddFileToQuarantineTask"

    restore_quarantine = prepare_restore_quarantine_file_endpoint(params)
    assert restore_quarantine["api"] == "api/v1.0/jsonrpc/quarantine/computers"
    assert restore_quarantine["body"]["method"] == "createRestoreQuarantineItemTask"
