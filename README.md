<p align="center">
  <img width="auto" height="120" src="./docs/fora.png">
</p>

<p align="center">
   <a href="https://pypi.python.org/pypi/fora"><img src="https://img.shields.io/pypi/v/fora?color=green" title="PyPI Version"></a>
   <a href="https://pepy.tech/project/fora"><img src="https://static.pepy.tech/personalized-badge/fora?period=total&units=abbreviation&left_color=grey&right_color=green&left_text=downloads" title="PyPI Downloads"></a>
   <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" title="MIT License"></a>
   <a href="https://oddlama.gitbook.io/fora"><img src="https://img.shields.io/badge/documentation-blue.svg" title="Documentation"></a>
</p>

## What is Fora?

Fora is an infrastructure and configuration management tool inspired by [Ansible](https://www.ansible.com) and [pyinfa](https://pyinfra.com).
Yet, it implements a drastically different approach to inventory management (and some other aspects), when compared to these well-known tools.
See [how it differs](https://oddlama.gitbook.io/fora/outlining-the-differences#how-is-fora-different-from-existing-tools) for more details.

## Installation & Quickstart

You can install Fora with pip:

```bash
pip install fora
```

Afterwards, you can use it to write scripts that can run operation or commands on a remote host.

```python
# deploy.py
from fora.operations import files, system

files.directory(
    name="Create a temporary directory",
    path="/tmp/hello")

system.package(
    name="Install neovim",
    package="neovim")
```

These scripts are executed against an inventory, or a specific remote host (usually via SSH).

```bash
fora root@example.com deploy.py
```

To start with your own (more complex) deploy, you can have Fora create a scaffolding in an empty directory. There are [different scaffoldings](https://oddlama.gitbook.io/fora/usage/introduction#deploy-structure) available for different use-cases.

```bash
fora --init minimal
```

Fora can do a lot more than this, which is explained in the [Introduction](https://oddlama.gitbook.io/fora/usage/introduction). If you are interested in how Fora is different from existing tools, have a look at [Outlining the differences](https://oddlama.gitbook.io/fora/outlining-the-differences).
