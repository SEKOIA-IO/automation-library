from sekoia_automation.module import Module

from virustotal.action_virustotal_getcomments import VirusTotalGetCommentsAction
from virustotal.action_virustotal_postcomment import VirusTotalPostCommentAction
from virustotal.action_virustotal_scandomain import VirusTotalScanDomainAction
from virustotal.action_virustotal_scanfile import VirusTotalScanFileAction
from virustotal.action_virustotal_scanhash import VirusTotalScanHashAction
from virustotal.action_virustotal_scanip import VirusTotalScanIPAction
from virustotal.action_virustotal_scanurl import VirusTotalScanURLAction
from virustotal.livehunt_notification_files_trigger import LivehuntNotificationFilesTrigger

if __name__ == "__main__":
    module = Module()

    module.register(VirusTotalScanFileAction, "virustotal_scan_file")
    module.register(VirusTotalScanHashAction, "virustotal_scan_hash")
    module.register(VirusTotalScanURLAction, "virustotal_scan_url")
    module.register(VirusTotalScanDomainAction, "virustotal_scan_domain")
    module.register(VirusTotalScanIPAction, "virustotal_scan_ip")
    module.register(VirusTotalPostCommentAction, "virustotal_post_comment")
    module.register(VirusTotalGetCommentsAction, "virustotal_get_comments")

    module.register(LivehuntNotificationFilesTrigger, "livehunt_notification_files_trigger")

    module.run()
