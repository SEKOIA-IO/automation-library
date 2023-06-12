from sekoia_automation.module import Module

from http_module.download_file_action import DownloadFileAction
from http_module.request_action import RequestAction

if __name__ == "__main__":
    module = Module()

    module.register(DownloadFileAction, "download-file")
    module.register(RequestAction, "request")

    module.run()
