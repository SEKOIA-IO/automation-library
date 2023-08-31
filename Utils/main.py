from sekoia_automation.module import Module

from utils.action_fileutils_readjsonfile import FileUtilsReadJSONFile
from utils.action_fileutils_readxmlfile import FileUtilsReadXMLFile


if __name__ == "__main__":
    module = Module()

    module.register(FileUtilsReadJSONFile, "fileutils_readjsonfile")
    module.register(FileUtilsReadXMLFile, "fileutils_readxmlfile")

    module.run()
