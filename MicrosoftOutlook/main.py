from microsoft_outlook_modules import MicrosoftOutlookModule
from microsoft_outlook_modules.action_delete_message import DeleteMessageAction
from microsoft_outlook_modules.action_download_attachments import DownloadAttachmentsAction
from microsoft_outlook_modules.action_export_message import ExportMessageAction
from microsoft_outlook_modules.action_extract_email import ExtractEmailAction
from microsoft_outlook_modules.action_forward_message import ForwardMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
from microsoft_outlook_modules.action_list_messages import ListMessagesAction
from microsoft_outlook_modules.action_move_message import MoveMessageAction
from microsoft_outlook_modules.action_search_messages import SearchMessagesAction
from microsoft_outlook_modules.action_send_message import SendMessageAction
from microsoft_outlook_modules.action_update_message import UpdateMessageAction
from microsoft_outlook_modules.connector_phishing_reports import PhishingReportsConnector

if __name__ == "__main__":
    module = MicrosoftOutlookModule()
    module.register(ForwardMessageAction, "action_forward_message")
    module.register(GetMessageAction, "action_get_message")
    module.register(DeleteMessageAction, "action_delete_message")
    module.register(UpdateMessageAction, "action_update_message")
    module.register(SendMessageAction, "action_send_message")
    module.register(SearchMessagesAction, "action_search_messages")
    module.register(MoveMessageAction, "action_move_message")
    module.register(ExtractEmailAction, "action_extract_email")
    module.register(DownloadAttachmentsAction, "action_download_attachments")
    module.register(ExportMessageAction, "action_export_message")
    module.register(ListMessagesAction, "action_list_messages")
    module.register(PhishingReportsConnector, "connector_phishing_reports")
    module.run()
