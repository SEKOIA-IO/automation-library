import requests_mock

from openai_module.base import OpenAIConfiguration, OpenAIModule
from openai_module.gpt import AskGPTAction


def test_ask_gpt():
    module = OpenAIModule()
    module.configuration = OpenAIConfiguration(api_key="fake_api_key")

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello! How can I assist you today?",
                        }
                    }
                ]
            },
        )
        action = AskGPTAction(module)
        results = action.run({"prompt": "Say hello"})

        assert results["response"] == "Hello! How can I assist you today?"
        assert mock.last_request.json() == {
            "messages": [{"content": "Say hello", "role": "user"}],
            "model": "gpt-3.5-turbo",
            "temperature": 0.2,
        }

        results = action.run(
            {
                "prompt": "Say hello",
                "model": "gpt-4-0314",
                "temperature": 2,
                "max_tokens": 100,
            }
        )

        assert results["response"] == "Hello! How can I assist you today?"
        assert mock.last_request.json() == {
            "messages": [{"content": "Say hello", "role": "user"}],
            "model": "gpt-4-0314",
            "temperature": 2,
            "max_tokens": 100,
        }
