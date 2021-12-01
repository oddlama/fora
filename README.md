[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

**ATTENTION: This project is currently in beta development. The API may still change at anytime.**

## About

Why?

- Fast execution (single ssh connection per host)
- Execution on multiple hosts is currently not parallelized
- Intended for writing small and clean deploys. (Need to configure 1000 hosts? this is probably the wrong tool.)
- Agentless.
- Lightweight. (everything included amounts to just about 2kLOC (compare pyinfra 10kLOC, ansible ???)
- No surprises (for loops work like they should, no magic applied).
   - Debugging experiece is just like writing python as usual.
- Fully typed

This looks similar to pyinfra. What are the differences?

We like pyinfra and encourage using it. It is probably the better tool for large deploys.
What sets this project apart is.
Developer oriented.
Main goal was to create a minimal and predictable scripting environment for remote hosts.
scripts are executed in-order, once for each host, as one would expect.
It's easy to write reusable scripts.
Diff output good.

Fora is a infrastructure and configuration management tool inspired by ansible.

- Requires python3.9 on all managed systems.
- Functions similar to ansible, but lets you write your deploys in pure python

## Installation

Fora requires `python>=3.9`.

## Quick example

Here is a simple `deploy.py` which creates a temporary directory and uploads a templated file.

```python
from fora.operations import files

files.directory(name="Create a temporary directory",
    path="/tmp/hello")

files.template_content(name="Save templated content to the directory",
    content="{{fora_managed}}\nHello from host {{host.name}}\n",
    dest="/tmp/hello/world")
```

This script can then be executed on any ssh host.

```bash
fora ssh://root@localhost deploy.py
```
Of course you can separately define inventories, groups and hosts for larger deploys.
