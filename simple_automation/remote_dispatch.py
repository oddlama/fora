#!/usr/bin/env python3

import sys
import os
import subprocess
from pwd import getpwnam, getpwuid

def resolve_script_path():
    """
    Guard script name resolution because the remote variant
    will not be executed from a file.
    """
    try:
        return os.path.realpath(__file__)
    except NameError:
        return "/dev/null"

# Save path to this script so we can easily upload it
# to our remote hosts
script_path = resolve_script_path()

def read_mode():
    """
    Read and return a mode (newline terminated string)
    """
    mode = sys.stdin.buffer.readline().decode('utf-8')
    if not mode:
        return None
    # Strip newline
    return mode[:-1]

def write_mode(mode):
    """
    Write a mode (newline terminated string)
    """
    sys.stdout.buffer.write(mode.encode('utf-8'))
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.flush()

def write_data(data):
    """
    Write arbirtary binary data (sends a length, newline, data)
    """
    sys.stdout.buffer.write(str(len(data)).encode('utf-8'))
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()

def write_str(s):
    """
    Write arbirtary string
    """
    write_data(s.encode('utf-8'))

def read_len():
    """
    Read a newline delimited length
    """
    l = int(sys.stdin.buffer.readline().decode('utf-8'))
    if l < 0 or l > 16*1024*1024*1024:
        exit(2)
    return l

def read_data():
    """
    Read arbirtary data
    """
    return sys.stdin.buffer.read(read_len())

def read_str():
    """
    Read arbirtary string
    """
    return read_data().decode('utf-8')

def read_str_list():
    """
    Read a string list
    """
    xs = []
    for _ in range(read_len()):
        xs.append(read_str())
    return xs

class ExecutionSettings:
    """
    Execution settings for the next command.
    """
    def __init__(self):
        self.uid = 0
        self.gid = 0
        self.umask = 0o077
        self.input = None

class Dispatcher:
    """
    The main dispatcher. Parses the protocol and executes commands.
    """
    def __init__(self):
        self.debug = False
        self.execution_settings = ExecutionSettings()

    def handle_set_debug(self):
        """
        Handles the debugging mode packet.
        If debugging is enabled, we will print every executed command and the relevant settings.
        """
        self.debug = read_str() == "true"
        write_mode("ok")

    def handle_set_user(self):
        """
        Handles the user mode packet.
        Validates the given uid / resolves a username, which will then be used for the next command.
        The gid will be set to the primary gid of that user.
        """
        user = read_str()
        try:
            pw = getpwnam(user)
        except KeyError:
            try:
                pw = getpwuid(int(user))
            except (KeyError, ValueError):
                exit(4)

        self.execution_settings.uid = pw.pw_uid
        self.execution_settings.gid = pw.pw_gid
        write_mode("ok")

    def handle_set_umask(self):
        """
        Handles the umask mode packet.
        The given umask will be used for the next command execution.
        """
        # Set the umask
        self.execution_settings.umask = int(read_str())
        write_mode("ok")

    def handle_set_input(self):
        """
        Handles the input mode packet.
        The given input will be used as stdin for the next command execution.
        """
        # Set input
        self.execution_settings.input = read_data()
        write_mode("ok")

    def run_command(self, command):
        """
        Runs a given command using the saved execution settings.
        The settings will be reset afterwards.
        """
        if self.debug:
            print(f"executing command={command} umask={self.execution_settings.umask} uid={self.execution_settings.uid} gid={self.execution_settings.gid}", file=sys.stderr, flush=True)

        cmd_input = None if self.execution_settings.input is None else self.execution_settings.input
        def child_preexec():
            """
            Sets umask and becomes the correct user.
            """
            try:
                os.umask(self.execution_settings.umask)
                os.setresgid(self.execution_settings.gid, self.execution_settings.gid, self.execution_settings.gid)
                os.setresuid(self.execution_settings.uid, self.execution_settings.uid, self.execution_settings.uid)
            except OSError as e:
                print(str(e), file=sys.stderr, flush=True)

        return subprocess.run(command, input=cmd_input, capture_output=True, preexec_fn=child_preexec, check=False)

    def handle_exec(self):
        """
        Handles the exec mode packet.
        Reads a command, and executes it. stdout and stderr will be
        captured and returned to the client.
        """
        # Execute a command
        command = read_str_list()
        completed_command = self.run_command(command)

        # Return output and status
        write_mode("ok")
        write_str(completed_command.stdout.decode('utf-8'))
        write_str(completed_command.stderr.decode('utf-8'))
        write_str(str(completed_command.returncode))

        if self.debug:
            print(f"stdout: {completed_command.stdout}", file=sys.stderr, flush=True)
            print(f"stderr: {completed_command.stderr}", file=sys.stderr, flush=True)
            print(f"rc: {str(completed_command.returncode)}", file=sys.stderr, flush=True)

        # Reset settings for next command
        self.execution_settings = ExecutionSettings()

    def handle_invalid_mode(self, mode):
        """
        Handles any invalid mode packet.
        Aborts the application.
        """
        # Invalid mode → abort
        print(f"Remote dispatcher received invalid mode '{mode}'. Aborting.", file=sys.stderr, flush=True)
        exit(3)

    def main(self):
        """
        Begin by changing directory to /tmp. Then listen for packets
        on stdin and loop until stdin is closed.
        """
        # Change into /tmp
        os.chdir("/tmp")

        handler = {
            "debug": self.handle_set_debug,
            "user": self.handle_set_user,
            "umask": self.handle_set_umask,
            "input": self.handle_set_input,
            "exec": self.handle_exec,
            }

        while True:
            # Read next mode, but end script on EOF
            mode = read_mode()
            if not mode:
                return

            handler.get(mode, lambda: self.handle_invalid_mode(mode))()

if __name__ == '__main__':
    Dispatcher().main()
