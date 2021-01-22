from simple_automation.vars import Vars
from simple_automation.remote_dispatch import script_path as local_remote_dispatch_script_path
from simple_automation.exceptions import RemoteExecError

from subprocess import CalledProcessError
import subprocess
import os
import sys

def _merge(source, destination):
    """
    Recursively merges two dictionaries source and destination.
    The source dictionary will only be read, but the destination dictionary will be overwritten.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            _merge(value, node)
        else:
            destination[key] = value

    return destination


class CompletedRemoteCommand:
    """
    A wrapper for the information returned by a remote command.
    """
    def __init__(self):
        self.stdout = None
        self.stderr = None
        self.return_code = None

class RemoteDispatcher:
    """
    A wrapper class around a process that executes the remote dispatch script.
    This will usually be an ssh command calling the script on a remote host,
    allowing us to send commands an receive output and return code information.
    """

    def __init__(self, context, command):
        self.context = context
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)

    def stop_and_wait(self):
        """
        Stops the remote dispatcher, and waits until it exists.
        """
        self.process.stdin.close()
        self.process.wait()
        self.process.stdout.close()

    def write_data(self, data):
        """
        Sends raw data to the remote process.
        """
        self.process.stdin.write(str(len(data)).encode('utf-8'))
        self.process.stdin.write(b'\n')
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def write_line(self, s):
        """
        Sends a line to the remote process.
        """
        self.process.stdin.write(s.encode('utf-8'))
        self.process.stdin.write(b'\n')
        self.process.stdin.flush()

    def write_str(self, s):
        """
        Sends the given string to the remote process.
        """
        self.write_data(s.encode('utf-8'))

    def write_str_list(self, xs):
        """
        Sends the given list of strings to the remote process.
        """
        self.write_line(str(len(xs)))
        for x in xs:
            self.write_str(x)

    def write_mode(self, mode):
        """
        Sends a mode to the remote dispatch process.
        """
        self.write_line(mode)

    def read_len(self):
        """
        Reads a length parameter from the remote process.
        """
        l = int(self.process.stdout.readline())
        if l < 0 or l > 16*1024*1024*1024:
            exit(2)
        return l

    def read_str(self):
        """
        Reads a string from the remote process.
        """
        return self.process.stdout.read(self.read_len()).decode('utf-8')

    def expect(self, s):
        """
        Waits until the given string is sent by the remote side.
        """
        self.process.stdin.flush()
        line = self.process.stdout.readline().decode('utf-8')
        if not line:
            raise Exception("unexpected EOL")
        line = line[:-1]
        if line != s:
            raise Exception(f"expected '{s}' but got '{line}'")

    def exec(self, command):
        """
        Executes the given command on the remote machine as the
        user and with the umask given by the attached context.
        """
        # Set user to execute as
        self.write_mode("user")
        self.write_str(self.context.as_user)
        self.expect("ok")

        # Set umask value
        self.write_mode("umask")
        self.write_str(str(self.context.umask_value))
        self.expect("ok")

        # Execute command and get output
        self.write_mode("exec")
        self.write_str_list(command)
        self.expect("ok")
        ret = CompletedRemoteCommand()
        ret.stdout = self.read_str()
        ret.stderr = self.read_str()
        ret.return_code = int(self.read_str())
        return ret


class Context:
    def __init__(self, host):
        self.host = host
        self.precomputed_vars = self._vars()
        self.remote_dispatcher = None

        # Defaults for remote actions
        self.defaults(user="root", umask=0o022, dir_mode=0o700, file_mode=0o600, owner="root", group="root")

    def __enter__(self):
        # Initialize ssh environment
        self.init_ssh()
        return self

    def __exit__(self, type, value, traceback):
        # Remove temporary files, and also do a safety check in
        # case anything goes horribly wrong.
        self.remote_dispatcher.stop_and_wait()
        if self.remote_temp_dir.startswith("/tmp"):
            self.exec_ssh_raw(["rm", "-rf", self.remote_temp_dir])

    def defaults(self, user, umask, dir_mode, file_mode, owner, group):
        """
        Overwrite the defaults for command execution on the remote machine.
        """
        self.user(user)
        self.umask(umask)
        self.mode(dir_mode, file_mode, owner, group)

    def umask(self, value):
        """
        Sets the umask for executed commands on the remote machine.
        """
        self.umask_value = value

    def user(self, user):
        """
        Sets the user to execute commands on the remote machine.
        """
        self.as_user = user

    def mode(self, dir_mode, file_mode, owner, group):
        """
        Sets default modes for created directories and files,
        as well as default owner and group
        """
        self.dir_mode = dir_mode
        self.file_mode = file_mode
        self.owner = owner
        self.group = group

    def transaction(self, name):
        """
        Begins a new transaction. Intended to be used in a 'with' statement.
        Each transaction will be shown to the user as a distinct unit.

        A transaction must record an initial state and a final state, and may
        return success or failure (+reason).

        A transaction should not actually alter the state of the remote,
        if context.pretend is set to True. In this case it should only examine
        and record what would be done.

        A transaction may give additional variables to success() and failure(),
        which will be stored for later use.
        """
        return Transaction(self, name)

    def _vars(self):
        """
        Merges all vars from inherited contexts (manager, groups, host) to
        provide a master dictionary for templating.
        """
        # Create merged dictionary
        d = self.host.manager.vars.copy()
        for group in self.host.groups:
            _merge(group.vars, d)
        _merge(self.host.vars, d)

        # Add procedural entries
        temp = Vars()
        temp.vars = d
        temp.set("context.host", self.host)
        return d

    def vars(self):
        return self.precomputed_vars

    def _base_ssh_command(self, command):
        """
        Constructs the base ssh command using the options supplied from the respective
        host that this context is bound to.
        """
        ssh_command = ["ssh"]
        ssh_command.extend(self.host.ssh_scp_params)
        ssh_command.append(f"ssh://{self.host.ssh_host}:{self.host.ssh_port}")
        ssh_command.extend(command)
        return ssh_command

    def _base_scp_command(self, local_path, remote_path, recursive=False):
        """
        Constructs the base scp command using the options supplied from the respective
        host that this context is bound to.
        """
        scp_command = ["scp"]
        if recursive:
            scp_command.append("-r")
        scp_command.extend(self.host.ssh_scp_params)
        scp_command.append(local_path)
        scp_command.append(f"scp://{self.host.ssh_host}:{self.host.ssh_port}/{remote_path}")
        return scp_command

    def init_ssh(self):
        """
        Initialize environment on the remote host (temporary directory, remote exec script),
        so we can more easily execute commands on the remote.
        """
        print(f"Establishing ssh connection to {self.host.ssh_host}")
        # Create temporary directory
        self.remote_temp_dir = self.exec_ssh_raw(["mktemp", "-d"]).stdout.decode("utf-8").split('\n')[0]
        # Upload remote dispatch script
        self.remote_dispatch_script_path = self.upload_file(local_remote_dispatch_script_path)
        # Start remote dispatch script
        self.remote_dispatcher = RemoteDispatcher(self, self._base_ssh_command(["python3", self.remote_dispatch_script_path]))

    def exec_ssh_raw(self, command):
        """
        Execute ssh to execute the given command on the remote host, directly via ssh.
        """
        return subprocess.run(self._base_ssh_command(command), check=True, capture_output=True)

    def upload_file(self, file):
        """
        Uploads the given file to the temporary directory on the remote host
        and returns the absolute path to the resulting file.
        """
        basename = os.path.basename(file)
        remote_file_path = os.path.join(self.remote_temp_dir, basename)
        subprocess.run(self._base_scp_command(file, remote_file_path), check=True)
        return remote_file_path

    def remote_exec(self, command, checked=False):
        """
        Execute ssh to execute the given command on the remote host,
        via our built-in remote dispatch script. If checked is True,
        it will throw an exception if the remote command returns an
        unsuccessful exit status.
        """
        # Execute the command via our existing remote session. Commands
        # are passed with NUL-terminated parameters, so we don't have to worry
        # about any quoting. This therefore ensures that there is no command
        # injection possible.
        ret = self.remote_dispatcher.exec(command)
        if checked and ret.return_code != 0:
            raise RemoteExecError(f"Remote command {command} was unsuccessful (code {ret.return_code})")
        return ret
