from sekoia_formatter_modules import SekoiaFormatterModule

from sekoia_formatter_modules.action_format import FormatAction

if __name__ == "__main__":
    module = SekoiaFormatterModule()
    module.register(FormatAction, "FormatAction")
    module.run()
