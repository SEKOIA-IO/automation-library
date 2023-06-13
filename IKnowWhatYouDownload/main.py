from sekoia_automation.module import Module

from iknowwhatyoudownload.action_iknow_ipexist import IKnowIPExistAction
from iknowwhatyoudownload.action_iknow_iphistory import IKnowIPHistoryAction
from iknowwhatyoudownload.action_iknow_iplist import IKnowIPListAction

if __name__ == "__main__":
    module = Module()

    module.register(IKnowIPHistoryAction, "ip_history")
    module.register(IKnowIPExistAction, "ip_exist")
    module.register(IKnowIPListAction, "ip_list")

    module.run()
