from bitwarden_module import BitwardenModule, NoopAction, NoopActionArguments


def test_module_name() -> None:
    module = BitwardenModule()
    assert module is not None


def test_noop_action_run_returns_ok_status() -> None:
    result = NoopAction.run(None, NoopActionArguments())
    assert result == {"status": "ok"}
