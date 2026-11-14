from easyvista_modules import EasyVistaModule
from easyvista_modules.account_validator import EasyVistaAccountValidator
from easyvista_modules.action.action_close_request_incident import CloseRequestIncident
from easyvista_modules.action.action_create_related_action_incident import CreateRelatedActionIncident
from easyvista_modules.action.action_create_request_incident import CreateRequestIncident
from easyvista_modules.action.action_create_task_request_incident import CreateTaskRequestIncident
from easyvista_modules.action.action_delete_request_document import DeleteRequestDocument
from easyvista_modules.action.action_get_non_terminated_actions_questionnaires import (
    GetNonTerminatedActionsQuestionnaires,
)
from easyvista_modules.action.action_get_request_incident_document import GetRequestIncidentDocument
from easyvista_modules.action.action_get_request_incident_documents import GetRequestIncidentDocuments
from easyvista_modules.action.action_get_specific_action_questionnaire import GetSpecificActionQuestionnaire
from easyvista_modules.action.action_restart_request_incident import RestartRequestIncident
from easyvista_modules.action.action_suspend_request_incident import SuspendRequestIncident
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident
from easyvista_modules.action.action_upload_attach_document_request_incident import UploadAttachDocumentRequestIncident
from easyvista_modules.action.action_view_request_incident import ViewRequestIncident
from easyvista_modules.action.action_view_request_incident_comment import ViewRequestIncidentComment
from easyvista_modules.action.action_view_request_incident_problem import ViewRequestIncidentProblem
from easyvista_modules.action.action_view_requests_incidents_list import ViewRequestsIncidentsList
from easyvista_modules.asset_connector.device_assets import EasyVistaDeviceAssetConnector


def main():
    module = EasyVistaModule()
    module.register_account_validator(EasyVistaAccountValidator)
    module.register(CreateRequestIncident, "easyvista_create_request_incident")
    module.register(UpdateRequestIncident, "easyvista_update_request_incident")
    module.register(CloseRequestIncident, "easyvista_close_request_incident")
    module.register(SuspendRequestIncident, "easyvista_suspend_request_incident")
    module.register(RestartRequestIncident, "easyvista_restart_request_incident")
    module.register(ViewRequestsIncidentsList, "easyvista_view_requests_incidents_list")
    module.register(ViewRequestIncident, "easyvista_view_request_incident")
    module.register(ViewRequestIncidentProblem, "easyvista_view_request_incident_problem")
    module.register(ViewRequestIncidentComment, "easyvista_view_request_incident_comment")
    module.register(UploadAttachDocumentRequestIncident, "easyvista_upload_attach_document_request_incident")
    module.register(GetRequestIncidentDocuments, "easyvista_get_request_incident_documents")
    module.register(GetRequestIncidentDocument, "easyvista_get_request_incident_document")
    module.register(DeleteRequestDocument, "easyvista_delete_request_document")
    module.register(CreateRelatedActionIncident, "easyvista_create_related_action_incident")
    module.register(CreateTaskRequestIncident, "easyvista_create_task_request_incident")
    module.register(GetNonTerminatedActionsQuestionnaires, "easyvista_get_non_terminated_actions_questionnaires")
    module.register(GetSpecificActionQuestionnaire, "easyvista_get_specific_action_questionnaire")
    module.register(EasyVistaDeviceAssetConnector, "easyvista_device_asset_connector")
    module.run()


if __name__ == "__main__":
    main()
