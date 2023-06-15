from sekoia_automation.module import Module

from gitmodule.triggers.file_changes import FileChangesTrigger
from gitmodule.triggers.new_commit import NewCommitTrigger

if __name__ == "__main__":
    module = Module()

    module.register(NewCommitTrigger, "new-commit-trigger")
    module.register(FileChangesTrigger, "file-changes-trigger")

    module.run()
