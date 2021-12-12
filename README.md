<p align="center">
  <img width="auto" height="120" src="./docs/fora.png">
</p>

<p align="center">
   <a href="https://pypi.python.org/pypi/fora"><img src="https://img.shields.io/pypi/v/fora?color=green" title="PyPI Version"></a>
   <a href="https://pepy.tech/project/fora"><img src="https://static.pepy.tech/personalized-badge/fora?period=total&units=abbreviation&left_color=grey&right_color=green&left_text=downloads" title="PyPI Downloads"></a>
   <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" title="MIT License"></a>
</p>

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

## Acknowledgements

The fora icon is slightly modified version of an image made by [Freepik](https://www.freepik.com) from [Flaticon](https://www.flaticon.com/).
