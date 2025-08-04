import uuid


def prepare_request_body(method: str, params: dict) -> dict:
    """
    Prepare the request body for the Bitdefender API.
    """
    return {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": str(uuid.uuid4()),
    }


def prepare_custom_scan_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the custom scan endpoint action.
    """
    return {
        "api": "api/v1.0/jsonrpc/network",
        "body": prepare_request_body("createScanTask", params),
    }


def prepare_isolate_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the isolate endpoint action.
    """
    return {
        "api": "api/v1.0/jsonrpc/incidents",
        "body": prepare_request_body("createIsolateEndpointTask", params),
    }


def prepare_deisolate_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the deisolate endpoint action.
    """
    return {
        "api": "api/v1.0/jsonrpc/incidents",
        "body": prepare_request_body("createRestoreEndpointFromIsolationTask", params),
    }


def prepare_kill_process_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the kill process action.
    """
    return {
        "api": "api/v1.0/jsonrpc/network",
        "body": prepare_request_body("killProcess", params),
    }


def prepare_get_block_list_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the get block list action.
    """
    return {
        "api": "api/v1.2/jsonrpc/incidents",
        "body": prepare_request_body("getBlocklistItems", params),
    }


def prepare_push_block_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the push block action.
    """
    return {
        "api": "api/v1.2/jsonrpc/incidents",
        "body": prepare_request_body("addToBlocklist", params),
    }


def prepare_add_quarantine_file_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the add file to quarantine action.
    """
    return {
        "api": "api/v1.0/jsonrpc/quarantine/computers",
        "body": prepare_request_body("createAddFileToQuarantineTask", params),
    }


def prepare_remove_block_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the remove block action.
    """
    return {
        "api": "api/v1.2/jsonrpc/incidents",
        "body": prepare_request_body("removeFromBlocklist", params),
    }


def prepare_restore_quarantine_file_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the restore quarantine file action.
    """
    return {
        "api": "api/v1.0/jsonrpc/quarantine/computers",
        "body": prepare_request_body("createRestoreQuarantineItemTask", params),
    }


def prepare_scan_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the scan endpoint action.
    """
    return {
        "api": "api/v1.0/jsonrpc/network",
        "body": prepare_request_body("createScanTask", params),
    }


def prepare_update_incident_status_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the update incident status action.
    """
    return {
        "api": "api/v1.0/jsonrpc/incidents",
        "body": prepare_request_body("changeIncidentStatus", params),
    }


def prepare_update_incident_note_endpoint(params: dict) -> dict:
    """
    Prepare the parameters for the update incident note action.
    """
    return {
        "api": "api/v1.0/jsonrpc/incidents",
        "body": prepare_request_body("updateIncidentNote", params),
    }
