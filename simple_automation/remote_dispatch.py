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
    x = sys.stdin.read(read_len())
    return x

def read_str_list():
    xs = []
    for i in range(read_len()):
        xs.append(read_str())
    return xs

def main():
    # Cd into temporary directory
    os.chdir(os.path.dirname(script_path))

    while True:
        mode = sys.stdin.readline()
        if not mode:
            # EOF
            return

        # Strip the newline
        mode = mode[:-1]
        if mode == "user":
            # Set the user to become
            user = read_str()
            write_mode("ok")
        elif mode == "umask":
            # Set the umask
            umask = read_str()
            write_mode("ok")
        elif mode == "exec":
            # Execute a command
            command = read_str_list()
            completed_command = subprocess.run(command, capture_output=True)
            write_mode("ok")
            write_str(completed_command.stdout.decode('utf-8'))
            write_str(completed_command.stderr.decode('utf-8'))
            write_str(str(completed_command.returncode))
        elif mode == "stop":
            exit(0)
        elif mode == "":
            # Skip empty modes
            continue
        else:
            # Invalid mode
            exit(3)

if __name__ == '__main__':
    main()
