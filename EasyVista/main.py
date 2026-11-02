from easyvista import EasyVistaModule
from easyvista.account_validator import EasyVistaAccountValidator
from easyvista.actions_documents import (
    DeleteRequestDocument,
    GetRequestIncidentDocument,
    GetRequestIncidentDocuments,
    UploadAttachDocumentRequestIncident,
)
from easyvista.actions_read import (
    GetNonTerminatedActionsQuestionnaires,
    GetSpecificActionQuestionnaire,
    ViewRequestIncident,
    ViewRequestIncidentComment,
    ViewRequestIncidentProblem,
    ViewRequestsIncidentsList,
)
from easyvista.actions_requests import (
    CloseRequestIncident,
    CreateRequestIncident,
    RestartRequestIncident,
    SuspendRequestIncident,
    UpdateRequestIncident,
)
from easyvista.actions_workflow import (
    CreateRelatedActionIncident,
    CreateTaskRequestIncident,
)


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
    module.run()


if __name__ == "__main__":
    main()
