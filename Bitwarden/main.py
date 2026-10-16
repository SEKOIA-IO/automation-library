from bitwarden_module import BitwardenModule, NoopAction

if __name__ == "__main__":
    module = BitwardenModule()
    module.register(NoopAction, "bitwarden_noop")
    module.run()
