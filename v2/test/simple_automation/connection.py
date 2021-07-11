"""
Provides the Context class and related methods.
"""

import base64
import subprocess
import sys

from simple_automation.remote_dispatch import script_path as local_remote_dispatch_script_path

class CompletedRemoteCommand:
    """
    A wrapper for the information returned by a remote command.
    """
    # pylint: disable=R0903
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

    def __init__(self, connection, command):
        self.connection = connection
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)

        # Set debugging mode
        self.write_mode("debug")
        self.write_str(str(self.connection.debug).lower())
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
            print("error: Recieved invalid length string! Aborting.", file=sys.stderr)
            sys.exit(2)
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

    # We name our argument input because thats how it's named in subprocess.run().
    # pylint: disable=W0622
    def exec(self, command, input=None, user=None, umask=None):
        """
        Executes the given command on the remote machine as the
        user and with the umask given by the attached connection.
        """
        # Set user to execute as
        self.write_mode("user")
        self.write_str(user or self.connection.user)
        self.expect("ok")

        # Set umask value
        self.write_mode("umask")
        self.write_str(str(umask or self.connection.umask))
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

class HostConnectionContext:
    def __init__(self, host):
        self.host = host

class Connection:
    def __init__(self, host):
        self.host = host
        self.remote_dispatcher = None

        # Initial defaults for remote actions.
        # TODO string modes better because not ambiguous.
        self.user: str = "root"
        self.umask = 0o077
        self.dir_mode = 0o700
        self.file_mode = 0o600
        self.owner = "root"
        self.group = "root"

    def __enter__(self):
        # Open the connection
        self._open()

        self.host.connection = self
        return self

    def __exit__(self, type_t, value, traceback):
        self.host.connection = None
        # Remove temporary files, and also do a safety check, so
        # this will never go horribly wrong.
        self._close()

    def _open(self):
        print(f"[[32m>[m] Establishing ssh connection to {self.host.ssh_host}")
        with open(local_remote_dispatch_script_path, 'rb') as f:
            remote_dispatcher_script_source_base64 = base64.b64encode(f.read()).decode('utf-8')
        # Upload and start remote dispatch script
        self.remote_dispatcher = RemoteDispatcher(self, self._base_ssh_command([f"python3 -c \"$(echo '{remote_dispatcher_script_source_base64}' | base64 -d)\""]))

    def _close(self):
        self.remote_dispatcher.stop_and_wait()

    def _base_ssh_command(self, command):
        """
        Constructs the base ssh command using the options supplied from the respective
        host that this context is bound to.
        """
        ssh_command = ["ssh"]
        ssh_command.extend(self.host.ssh_opts)
        if self.host.ssh_host.startswith("ssh://"):
            ssh_command.append(self.host.ssh_host)
        else:
            ssh_command.append(f"ssh://{self.host.ssh_host}:{self.host.ssh_port}")
        ssh_command.extend(command)
        return ssh_command

    def exec_ssh_raw(self, command):
        """
        Execute ssh to execute the given command on the remote host, directly via ssh.

        Parameters
        ----------
        command : list[str]
            The command to execute on the remote.

        Returns
        -------
        subprocess.CompletedProcess
            The completed subprocess
        """
        return subprocess.run(self._base_ssh_command(command), check=True, capture_output=True)

    # We name our argument input because thats how it's named in subprocess.run().
    def remote_exec(self, command, checked=False, input=None, error_verbosity=None, user=None, umask=None, verbosity=None):
        """
        Execute ssh to execute the given command on the remote host,
        via our built-in remote dispatch script. If checked is True,
        it will throw an exception if the remote command returns an
        unsuccessful exit status. checked=True also implies a default error_verbosity=0
        and verbosity=2.

        If both verbosity and error_verbosity trigger, the output will only be printed once.

        Parameters
        ----------
        command : list[str]
            The command to execute on the remote.
        checked : bool, optional
            If true, an exception will be raised if the command fails. Defaults to false.
        input : bytes, optional
            If not None, this will be passed to the command as stdin.
        user : str, optional
            A specific user to execute the command as. Defaults to the user set in the context.
        umask : int, optional
            A specific umask to execute the command with. Defaults to the umask set in the context.
        verbosity : int, optional
            If verbosity is not None and self.verbose >= verbosity, the command
            output will be printed. Read: verbosity is the number of -v flags
            needed so that the command's output will be shown. If verbosity is not given,
            the output will never be shown.
        error_verbosity : int, optional
            Same as verbosity, but only triggers when the command fails.
            E.g. calling with error_verbosity=1 causes both stdout
            and stderr to be printed, if the command fails and at least -v was given.

        Returns
        -------
        CompletedRemoteCommand
            The completed remote command
        """
        # Execute the command via our existing remote session. Commands
        # are passed with NUL-terminated parameters, so we don't have to worry
        # about any quoting. This therefore ensures that there is no command
        # injection possible.
        ret = self.remote_dispatcher.exec(command, input, user, umask)

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
