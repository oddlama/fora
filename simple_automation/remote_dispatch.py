#!/usr/bin/env python3

import sys
import os
import subprocess

# Save path to this script so we can easily upload it
# to our remote hosts
script_path = os.path.realpath(__file__)

def read_mode():
    mode = sys.stdin.buffer.readline().decode('utf-8')
    if not mode:
        return None
    # Strip newline
    return mode[:-1]

def write_mode(mode):
    sys.stdout.buffer.write(mode.encode('utf-8'))
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.flush()

def write_data(data):
    sys.stdout.buffer.write(str(len(data)).encode('utf-8'))
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()

def write_str(s):
    write_data(s.encode('utf-8'))

def read_len():
    l = int(sys.stdin.buffer.readline().decode('utf-8'))
    if l < 0 or l > 16*1024*1024*1024:
        exit(2)
    return l

def read_data():
    return sys.stdin.buffer.read(read_len())

def read_str():
    return read_data().decode('utf-8')

def read_str_list():
    xs = []
    for i in range(read_len()):
        xs.append(read_str())
    return xs

class ExecutionSettings:
    def __init__(self):
        self.user = "root"
        self.umask = 0o077
        self.input = None

class Dispatcher:
    def __init__(self):
        self.debug = False
        self.execution_settings = ExecutionSettings()

    def handle_set_debug(self):
        # Set the user to become
        self.debug = read_str() == "true"
        write_mode("ok")

    def handle_set_user(self):
        # Set the user to become
        self.execution_settings.user = read_str()
        write_mode("ok")

    def handle_set_umask(self):
        # Set the umask
        self.execution_settings.umask = int(read_str())
        write_mode("ok")

    def handle_set_input(self):
        # Set input
        self.execution_settings.input = read_data()
        write_mode("ok")

    def run_command(self, command):
        if self.debug:
            print(f"executing command={command} umask={self.execution_settings.umask} user={self.execution_settings.user}", file=sys.stderr, flush=True)

        # TODO become user
        os.umask(self.execution_settings.umask)
        input = None if self.execution_settings.input is None else self.execution_settings.input
        return subprocess.run(command, input=input, capture_output=True)

    def handle_exec(self):
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
        execution_settings = ExecutionSettings()

    def handle_invalid_mode(self):
        # Invalid mode → abort
        print(f"Remote dispatcher received invalid mode '{mode}'. Aborting.", file=sys.stderr, flush=True)
        exit(3)

    def main(self):
        # Cd into temporary directory
        os.chdir(os.path.dirname(script_path))

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

            handler.get(mode, self.handle_invalid_mode)()

if __name__ == '__main__':
    Dispatcher().main()
