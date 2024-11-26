from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_email_sec import TrendMicroEmailSecurityConnector
from trendmicro_modules.trigger_vision import TrendMicroVisionOneConnector

if __name__ == "__main__":
    module = TrendMicroModule()
    module.register(TrendMicroEmailSecurityConnector, "trend_micro_email_security")
    module.register(TrendMicroVisionOneConnector, "trend_micro_vision_one")
    module.run()
