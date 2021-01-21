#!/usr/bin/env python3

import sys
import os
import subprocess

# Save path to this script so we can easily upload it
# to our remote hosts
script_path = os.path.realpath(__file__)

def write_mode(mode):
    sys.stdout.write(mode)
    sys.stdout.write('\n')
    sys.stdout.flush()

def write_str(s):
    sys.stdout.write(str(len(s)))
    sys.stdout.write('\n')
    sys.stdout.write(s)
    sys.stdout.flush()

def read_len():
    l = int(sys.stdin.readline())
    if l < 0 or l > 16*1024*1024*1024:
        exit(2)
    return l

def read_str():
    return sys.stdin.read(read_len())

def read_str_list():
    xs = []
    for i in range(read_len()):
        xs.append(read_str())
    return xs

class Dispatcher:
    def __init__(self):
        self.execution_settings = ExecutionSettings()

    def handle_set_user(self):
        # Set the user to become
        self.execution_settings.user = read_str()
        write_mode("ok")

    def handle_set_umask(self):
        # Set the umask
        self.execution_settings.umask = int(read_str())
        write_mode("ok")

    def run_command(self, command):
        print(f"executing {command=}", file=sys.stderr, flush=True)
        subprocess.run(command, capture_output=True)

    def handle_exec(self):
        # Execute a command
        command = read_str_list()
        completed_command = run_command(command)

        # Return output and status
        write_mode("ok")
        write_str(completed_command.stdout.decode('utf-8'))
        write_str(completed_command.stderr.decode('utf-8'))
        write_str(str(completed_command.returncode))

        # Reset settings for next command
        execution_settings = ExecutionSettings()

    def main(self):
        # Cd into temporary directory
        os.chdir(os.path.dirname(script_path))

        while True:
            # Read next mode
            mode = sys.stdin.readline()

            # End script on EOF
            if not mode:
                return

            # Strip the newline
            mode = mode[:-1]
            if mode == "user":
                handle_set_user()
            elif mode == "umask":
                handle_set_umask()
            elif mode == "exec":
                handle_exec()
            elif mode == "":
                # Skip empty modes
                continue
            else:
                # Invalid mode → abort
                exit(3)

if __name__ == '__main__':
    Dispatcher().main()
