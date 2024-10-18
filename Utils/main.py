from sekoia_automation.module import Module

from utils.action_fileutils_readjsonfile import FileUtilsReadJSONFile
from utils.action_fileutils_readxmlfile import FileUtilsReadXMLFile
from utils.action_utils_wait import UtilsWait
from utils.action_get_current_time import GetCurrentTimeAction
from utils.password_generator import PasswordGenerator
from utils.action_groupby import GroupProcessor

if __name__ == "__main__":
    module = Module()

    module.register(FileUtilsReadJSONFile, "fileutils_readjsonfile")
    module.register(FileUtilsReadXMLFile, "fileutils_readxmlfile")
    module.register(UtilsWait, "utils_wait")
    module.register(GetCurrentTimeAction, "GetCurrentTimeAction")
    module.register(PasswordGenerator, "password_generator")
    module.register(GroupProcessor, "action_groupby")

    module.run()
