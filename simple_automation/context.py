from simple_automation.exceptions import RemoteExecError
from simple_automation.remote_dispatch import script_path as local_remote_dispatch_script_path
from simple_automation.transaction import Transaction
from simple_automation.vars import Vars
from simple_automation.utils import merge_dicts, align_ellipsis, ellipsis

import base64
import os
import subprocess
import sys

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

        # Set debugging mode
        self.write_mode("debug")
        self.write_str(str(self.context.debug).lower())
        self.expect("ok")

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
        l = int(self.process.stdout.readline().decode('utf-8'))
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

    def exec(self, command, input=None):
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

        # Set input value
        if input is not None:
            self.write_mode("input")
            self.write_str(str(input))
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
    """
    A context is a wrapper object around a host and an ssh connection to that
    host. It is used to execute commands on the remote machine, and tracks state
    over the connection lifetime.
    """

    def __init__(self, manager, host):
        """
        Initializes a new context. For internal use only.
        """
        self.manager = manager
        self.host = host

        self._precompute_vars()
        self.remote_dispatcher = None

        # A cache for internal purposes only.
        self.cache = {}

        # Initial defaults for remote actions. Should be called by every task.
        self.defaults(user="root", umask=0o022, dir_mode=0o700, file_mode=0o600, owner="root", group="root")

    @property
    def pretend(self):
        """
        Forwards the corresponding variable from the associated manager.
        """
        return self.manager.pretend

    @property
    def verbose(self):
        """
        Forwards the corresponding variable from the associated manager.
        """
        return self.manager.verbose

    @property
    def debug(self):
        """
        Forwards the corresponding variable from the associated manager.
        """
        return self.manager.debug

    def __enter__(self):
        """
        Initializes the ssh connection and environment to the host.
        """
        # Initialize ssh environment
        self.init_ssh()
        return self

    def __exit__(self, type, value, traceback):
        """
        Initializes the ssh connection to the host.
        """
        # Remove temporary files, and also do a safety check, so
        # this will never go horribly wrong.
        self.remote_dispatcher.stop_and_wait()

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

    def transaction(self, title, name):
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
        return Transaction(self, title, name)

    def _precompute_vars(self):
        """
        Merges all vars from inherited contexts (manager, groups, host) to
        provide a master dictionary for templating.
        """
        # Create merged dictionary
        d = self.manager.vars.copy()
        for group in self.host.groups:
            merge_dicts(group.vars, d)
        merge_dicts(self.host.vars, d)

        # Add procedural entries
        self.merged_vars = Vars()
        self.merged_vars.vars = d
        self.merged_vars.set("context.manager", self.manager)
        self.merged_vars.set("context.host", self.host)

    @property
    def vars(self):
        return self.merged_vars

    @property
    def vars_dict(self):
        return self.merged_vars.vars

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
        scp_command = ["scp", "-q"]
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
        print(f"[[32m>[m] Establishing ssh connection to {self.host.ssh_host}")
        with open(local_remote_dispatch_script_path, 'rb') as f:
            remote_dispatcher_script_source_base64 = base64.b64encode(f.read()).decode('utf-8')
        # Upload and start remote dispatch script
        self.remote_dispatcher = RemoteDispatcher(self, self._base_ssh_command([f"python3 -c \"$(echo '{remote_dispatcher_script_source_base64}' | base64 -d)\""]))

    def exec_ssh_raw(self, command):
        """
        Execute ssh to execute the given command on the remote host, directly via ssh.
        """
        return subprocess.run(self._base_ssh_command(command), check=True, capture_output=True)

    def remote_exec(self, command, checked=False, input=None, error_verbosity=None, verbosity=None):
        """
        Execute ssh to execute the given command on the remote host,
        via our built-in remote dispatch script. If checked is True,
        it will throw an exception if the remote command returns an
        unsuccessful exit status. checked=True also implies a default error_verbosity=0
        and verbosity=2.

        If verbosity is not None and self.verbose >= verbosity, the command
        output will be printed. Read: verbosity is the number of -v flags
        needed so that the command's output will be shown. If verbosity is not given,
        the output will never be shown.

        error_verbosity is the same as verbosity, but only triggers when the
        command failed. E.g. calling with error_verbosity=1 causes both stdout
        and stderr to be printed, if the command fails and at least -v was given.

        If both verbosity and error_verbosity trigger, the output will only be printed once.
        """
        # Execute the command via our existing remote session. Commands
        # are passed with NUL-terminated parameters, so we don't have to worry
        # about any quoting. This therefore ensures that there is no command
        # injection possible.
        ret = self.remote_dispatcher.exec(command, input)

        if checked:
            if error_verbosity is None:
                error_verbosity = 0
            if verbosity is None:
                verbosity = 2

        do_print_verbosity = verbosity is not None and self.verbose >= verbosity
        do_print_error_verbosity = ret.return_code != 0 and (error_verbosity is not None and self.verbose >= error_verbosity)

        # Show the output if the verbosity demands it
        if do_print_verbosity or do_print_error_verbosity:
            status_char = "[32m>[m" if ret.return_code == 0 else "[31m>[m"
            print(f"\n[{status_char}] ---- REMOTE COMMAND: {command} ----")
            print(f"[{status_char}] exit code: {ret.return_code}")
            print(f"[{status_char}] stdout:")
            print(ret.stdout, end="")
            print(f"[{status_char}] stderr:")
            print(ret.stderr, end="")

        # Check the output
        if checked and ret.return_code != 0:
            raise RemoteExecError(command, ret)

        return ret

    def run_task(self, registered_task_class):
        """
        Runs the registered instance (see Manager) for the given task class.
        """
        instance = self.manager.tasks.get(registered_task_class.identifier, None)
        if not instance:
            raise LogicError(f"Cannot run unregistered task {registered_task_class}")
        if not isinstance(instance, registered_task_class):
            raise LogicError("Cannot run unrelated task with the same identifier as a registered task.")
        instance.exec(self)

    def print_transaction_title(self, transaction, title_color, status_char):
        """
        Prints the transaction title and name
        """
        title = align_ellipsis(transaction.title, 10)
        name_align_at = 30 * (1 + (len(transaction.name) // 30))
        name = f"{transaction.name:<{name_align_at}}"
        print(f"[{status_char}] {title_color}{title}[m {name}", end="", flush=True)

    def print_transaction_early(self, transaction):
        """
        Prints the transaction summary early (i.e. without changes)
        """
        title_color = "[1;33m"
        status_char = "[33m?[m"

        # Print title and name
        self.print_transaction_title(transaction, title_color, status_char)

    def print_transaction(self, transaction):
        """
        Prints the transaction summary
        """
        if transaction.success:
            if transaction.changed:
                title_color = "[1;34m"
                status_char = "[32m+[m"
            else:
                title_color = "[1m"
                status_char = "[37m.[m"
        else:
            title_color = "[1;31m"
            status_char = "[1;31m![m"

        # Print title and name, overwriting the transitive status
        print("\r", end="")
        self.print_transaction_title(transaction, title_color, status_char)

        # Print key: value pairs with changes
        state_infos = []
        for k,final_v in transaction.final_state.items():
            initial_v = transaction.initial_state[k]

            # Add ellipsis on long strings
            str_k = ellipsis(k, 12)
            str_initial_v = ellipsis(str(initial_v), 9)
            str_final_v = ellipsis(str(final_v), 9)

            if initial_v == final_v:
                if self.verbose >= 1:
                    entry_str = f"[37m{str_k}: {str_initial_v}[m"
                    state_infos.append(entry_str)
            else:
                entry_str = f"[33m{str_k}: [31m{str_initial_v}[33m → [32m{str_final_v}[m"
                state_infos.append(entry_str)
        print("[37m,[m ".join(state_infos))

        if self.verbose >= 1 and transaction.extra_info is not None:
            extra_infos = []
            for k,v in transaction.extra_info.items():
                extra_infos.append(f"[37m{str(k)}: {str(v)}[m")
            print(" " * 15 + "[37m,[m ".join(extra_infos))
