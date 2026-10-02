from sekoia_automation.module import Module

from http_module.action_download_file import DownloadFileAction
from http_module.action_request import RequestAction

if __name__ == "__main__":
    module = Module()

    module.register(DownloadFileAction, "download-file")
    module.register(RequestAction, "request")

    module.run()
