from censys.base import CensysIndex

from censys_module.base import CensysAction


class ViewAction(CensysAction):
    def execute_request(self, index_class: CensysIndex, arguments: dict):
        return index_class.view(arguments["item"])
