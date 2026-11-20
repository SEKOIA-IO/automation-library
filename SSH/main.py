from ssh_remote import SSHModule
from ssh_remote.actions import RunSSHCommand, RunSSHScript

if __name__ == "__main__":
    module = SSHModule()
    module.register(RunSSHCommand, "run_ssh_command")
    module.register(RunSSHScript, "run_ssh_script")
    module.run()
