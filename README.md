[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

**ATTENTION: This project is currently in beta development. The API may still change at anytime.**

## About

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
