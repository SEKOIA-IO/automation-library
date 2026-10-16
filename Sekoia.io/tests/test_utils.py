from sekoiaio.utils import user_agent


def test_user_agent():
    user_agent_orig = user_agent()

    agent, version = user_agent_orig.split("/", 1)
    assert agent == "symphony-module-sekoia.io"
    assert version != "unknown"


def test_user_agent_without_manifest(monkeypatch, tmp_path):
    class FakeSettings:
        base_directory = tmp_path

    monkeypatch.setattr("sekoiaio.utils.Settings", FakeSettings)
    user_agent.cache_clear()
    try:
        assert user_agent() == "symphony-module-sekoia.io/unknown"
    finally:
        user_agent.cache_clear()
