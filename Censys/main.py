from sekoia_automation.module import Module

from censys_module.report import ReportAction
from censys_module.search import SearchAction
from censys_module.view import ViewAction

if __name__ == "__main__":
    module = Module()

    module.register(SearchAction, "censys-search")
    module.register(ViewAction, "censys-view")
    module.register(ReportAction, "censys-report")

    module.run()
