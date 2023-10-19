from getcurrenttime_modules import GetcurrenttimeModule

from getcurrenttime_modules.action_get_current_time import GetCurrentTimeAction


if __name__ == "__main__":
    module = GetcurrenttimeModule()
    module.register(GetCurrentTimeAction, "GetCurrentTimeAction")
    module.run()
