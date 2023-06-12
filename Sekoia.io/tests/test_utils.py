from sekoiaio.utils import user_agent


def test_user_agent():
    user_agent_orig = user_agent()

    agent, version = user_agent_orig.split("/", 1)
    assert agent == "symphony-module-sekoia.io"
    assert version != "unknown"
