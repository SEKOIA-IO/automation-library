from bitwarden_module import BitwardenModule


def test_module_name() -> None:
    module = BitwardenModule()
    assert module is not None
