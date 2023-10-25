from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_email_sec import TrendMicroEmailSecurityConnector

if __name__ == "__main__":
    module = TrendMicroModule()
    module.register(TrendMicroEmailSecurityConnector, "trend_micro_email_security")
    module.run()
