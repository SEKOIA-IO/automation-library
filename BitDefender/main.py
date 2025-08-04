from sekoia_automation.module import Module

from bitdefender.actions import (
    IsolateEndpointAction,
    DeisolateEndpointAction,
    CustomScanEndpointAction,
    ScanEndpointAction,
    QuarantineFileAction,
    KillProcessAction,
    UpdateCommentIncidentAction,
    UpdateIncidentStatusAction,
    PushBlockAction,
    RemoveBlockAction,
    RestoreQuarantineFileAction,
    GetBlockListAction,
)

if __name__ == "__main__":
    module = Module()
    module.register(IsolateEndpointAction, "bitdefender_gravity_zone_isolate_endpoint")
    module.register(
        DeisolateEndpointAction, "bitdefender_gravity_zone_deisolate_endpoint"
    )
    module.register(
        CustomScanEndpointAction, "bitdefender_gravity_zone_custom_scan_endpoint"
    )
    module.register(ScanEndpointAction, "bitdefender_gravity_zone_scan_endpoint")
    module.register(QuarantineFileAction, "bitdefender_gravity_quarantine_file")
    module.register(KillProcessAction, "bitdefender_gravity_zone_kill_process")
    module.register(
        UpdateCommentIncidentAction, "bitdefender_gravity_zone_update_comment_incident"
    )
    module.register(
        UpdateIncidentStatusAction, "bitdefender_gravity_zone_update_incident_status"
    )
    module.register(GetBlockListAction, "bitdefender_gravity_zone_get_block_list")
    module.register(PushBlockAction, "bitdefender_gravity_zone_push_connection_block")
    module.register(PushBlockAction, "bitdefender_gravity_zone_push_hash_block")
    module.register(PushBlockAction, "bitdefender_gravity_zone_push_path_block")
    module.register(RemoveBlockAction, "bitdefender_gravity_zone_remove_block")
    module.register(
        RestoreQuarantineFileAction, "bitdefender_gravity_restore_quarantine_file"
    )
    module.register()
    module.run()
