from cortex_module.actions.action_scan_endpoints import ScanEndpointsAction


class AbortScanEndpointsAction(ScanEndpointsAction):
    """
    This action aborts ongoing endpoint scans
    """

    request_uri = "public_api/v1/endpoints/abort_scan"
