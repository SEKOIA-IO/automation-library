from test_mehidine_modules import Test_MehidineModule

from test_mehidine_modules.action_request import Request


if __name__ == "__main__":
    module = Test_MehidineModule()
    module.register(Request, "Request")
    module.run()
