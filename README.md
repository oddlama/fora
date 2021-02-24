[Introduction](https://simple_automation.oddlama.org/en/latest/contents/introduction.html) \|
[Documentation](https://simple_automation.oddlama.org/en/latest)

[![PyPI](https://img.shields.io/pypi/v/simple_automation.svg)](https://pypi.org/pypi/simple_automation/)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Docs](https://readthedocs.org/projects/simple_automation/badge/?version=latest)](https://simple_automation.oddlama.org/en/latest/?badge=latest)

# About simple automation

Simple automation is an ansible-inspired infrastructure and configuration management tool,
but with a focus on minimalism and simplicity. Its intended uses are small-scale machine administation, system configuration tracking,
or even just dotfiles management. Although it can certainly be used to administer larger
infrastructures.

If you want a high level overview of the different library components
and how they work together, please have a look at the [Architecture](https://simple_automation.oddlama.org/simple_automation/en/latest/api/architecture.html) page.

[x] Focus on minimalism and simplicity. It's easy to extend functionality, and there is no bullshit.
[x] Use python to write your configuration and don't be limited by a domain specific language
[x] Provides concicse, readable output
[x] Store your secrets in vaults encrypted symmetically or by gpg
[x] Few dependencies: jinja2, pycryptodome (if you use symmetically encrypted vaults)
[x] No remote dependencies except for python
[x] Easily track your system's state by having arbitrary files and directories checked into a git repository automatically.

## Installation

Use can use pip to install simple_automation. If you want to help maintaining a package
for your favourite distribution, feel free to reach out.

```bash
pip install simple_automation
```

You will need at least python 3.7.

## Quick example

```python
#!/usr/bin/env python3

from simple_automation import run_inventory, Inventory, Task
from simple_automation.transactions.basic import copy, directory, template

# -------- Define a task --------
class TaskZsh(Task):
    identifier = "zsh"
    description = "Installs global zsh configuration"

    def run(self, context):
        # Execute as root and set permission defaults
        context.defaults(user="root", umask=0o022, dir_mode=0o755, file_mode=0o644,
                         owner="root", group="root")

        # Template the zshrc, copy the zprofile
        directory(context, path="/etc/zsh")
        template(context, src="templates/zsh/zshrc.j2", dst="/etc/zsh/zshrc")
        copy(context, src="files/zsh/zprofile", dst="/etc/zsh/zprofile")

# -------- Setup your inventory --------
class MySite(Inventory):
    tasks = [TaskZsh]

    def register_inventory(self):
        self.manager.add_host("my_home_pc", ssh_host="root@localhost")

    def run(self, context):
        context.run_task(TaskZsh)

# -------- Run the inventory --------
if __name__ == "__main__":
    run_inventory(MySite)
```

For more sophisticated examples have a look at the [Examples](https://simple_automation.oddlama.org/en/latest/contents/examples.html) section in the
documentation.
