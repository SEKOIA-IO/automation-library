import openai
from pydantic import BaseModel, Field
from sekoia_automation.action import Action

from openai_module.base import OpenAIModule


class AskGPTArguments(BaseModel):
    prompt: str
    temperature: float = Field(
        0.2,
        ge=0,
        le=2,
        description="What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic.",  # noqa: E501
    )
    model: str = Field(
        "gpt-3.5-turbo",
        description="ID of the model to use. See the model endpoint compatibility table (https://platform.openai.com/docs/models/model-endpoint-compatibility) for details on which models work with the Chat API.",  # noqa: E501
    )
    max_tokens: int | None = Field(
        None,
        description="The maximum number of tokens to generate in the chat completion. Default is no limit",
    )


class AskGPTResults(BaseModel):
    response: str


class AskGPTAction(Action):
    name = "Ask GPT"
    description = "Use an OpenAI GPT model to provide an answer to any prompt"
    module: OpenAIModule
    results_model = AskGPTResults

    def run(self, arguments: AskGPTArguments):
        # Set the API Key to use
        openai.api_key = self.module.configuration.api_key

        # Send the prompt and get response
        params = {
            "model": arguments.model,
            "messages": [{"role": "user", "content": arguments.prompt}],
            "temperature": arguments.temperature,
        }

        if arguments.max_tokens:
            params["max_tokens"] = arguments.max_tokens

        results = openai.ChatCompletion.create(**params)

        return {"response": results.choices[0].message.content}
