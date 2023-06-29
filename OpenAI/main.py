from openai_module.base import OpenAIModule
from openai_module.gpt import AskGPTAction

if __name__ == "__main__":
    module = OpenAIModule()
    module.register(AskGPTAction, "AskGPTAction")
    module.run()
