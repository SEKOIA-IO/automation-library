from sekoia_automation.module import Module

from onyphe.action_onyphe_ctl import OnypheCtlAction
from onyphe.action_onyphe_datascan import OnypheDatascanAction
from onyphe.action_onyphe_forward import OnypheForwardAction
from onyphe.action_onyphe_geoloc import OnypheGeolocAction
from onyphe.action_onyphe_inetnum import OnypheInetnumAction
from onyphe.action_onyphe_ip import OnypheIpAction
from onyphe.action_onyphe_md5 import OnypheMD5Action
from onyphe.action_onyphe_onionscan import OnypheOnionscanAction
from onyphe.action_onyphe_pastries import OnyphePastriesAction
from onyphe.action_onyphe_reverse import OnypheReverseAction
from onyphe.action_onyphe_sniffer import OnypheSnifferAction
from onyphe.action_onyphe_synscan import OnypheSynscanAction
from onyphe.action_onyphe_threatlist import OnypheThreatlistAction

if __name__ == "__main__":
    module = Module()

    module.register(OnypheGeolocAction, "onyphe_geoloc")
    module.register(OnypheIpAction, "onyphe_ip")
    module.register(OnypheInetnumAction, "onyphe_inetnum")
    module.register(OnypheThreatlistAction, "onyphe_threatlist")
    module.register(OnyphePastriesAction, "onyphe_pastries")
    module.register(OnypheSynscanAction, "onyphe_synscan")
    module.register(OnypheDatascanAction, "onyphe_datascan")
    module.register(OnypheReverseAction, "onyphe_reverse")
    module.register(OnypheForwardAction, "onyphe_forward")
    module.register(OnypheSnifferAction, "onyphe_sniffer")
    module.register(OnypheCtlAction, "onyphe_ctl")
    module.register(OnypheMD5Action, "onyphe_md5")
    module.register(OnypheOnionscanAction, "onyphe_onionscan")

    module.run()
