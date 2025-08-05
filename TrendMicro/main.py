from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_email_sec import TrendMicroEmailSecurityConnector
from trendmicro_modules.trigger_vision_one_oat import TrendMicroVisionOneOATConnector
from trendmicro_modules.trigger_vision_one_workbench import TrendMicroVisionOneWorkbenchConnector

if __name__ == "__main__":
    module = TrendMicroModule()
    module.register(TrendMicroEmailSecurityConnector, "trend_micro_email_security")
    module.register(TrendMicroVisionOneWorkbenchConnector, "trend_micro_vision_one_workbench")
    module.register(TrendMicroVisionOneOATConnector, "trend_micro_vision_one_oat")
    module.run()
