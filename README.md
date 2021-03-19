[![PyPI](https://img.shields.io/pypi/v/simple_automation.svg)](https://pypi.org/pypi/simple_automation/)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Docs](https://readthedocs.org/projects/simple-automation/badge/?version=latest)](https://simple-automation.oddlama.org/en/latest/?badge=latest)

<p align="center">
  <img src="./docs/imgs/logo.svg" height="100" width="auto" />
</p>

[Introduction](https://simple-automation.oddlama.org/en/latest/contents/introduction.html) \|
[Documentation](https://simple-automation.oddlama.org/en/latest)

# About simple automation

**ATTENTION: This project is currently in beta development. The API may change at anytime until we reach version 1.0.0.**

Simple automation is an ansible-inspired infrastructure and configuration management tool,
but with a focus on minimalism and simplicity. Its intended uses are small-scale machine administation, system configuration tracking,
or even just dotfiles management. Although it can certainly be used to administer larger
infrastructures.

If you want a high level overview of the different library components
and how they work together, please have a look at the [Architecture](https://simple-automation.oddlama.org/en/latest/api/architecture.html) page.

- [x] Focus on minimalism and simplicity. It's easy to extend functionality, and there is no bullshit.
- [x] Use python to write your configuration and don't be limited by a domain specific language
- [x] Provides concicse, readable output
- [x] Store your secrets in vaults encrypted symmetically or by gpg
- [x] Few dependencies: jinja2, pycryptodome (if you use symmetically encrypted vaults)
- [x] No remote dependencies except for python
- [x] Easily track your system's state by having arbitrary files and directories checked into a git repository automatically.

## Installation

You can use pip to install simple_automation. If you want to help maintaining a package
for your favourite distribution, feel free to reach out.

Simple automation requires `python>=3.9`.

```bash
pip install simple_automation
```

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
        # Change permission defaults
        with context.defaults(umask=0o022, dir_mode=0o755, file_mode=0o644):
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

Possible output:
```
[>] Establishing ssh connection to root@localhost

[*] >>>> Task: zsh <<<<
[+] dir        /etc/zsh                      mode: 750 → 755
[+] template   /etc/zsh/zshrc                sha512sum: 3d48b060… → fac69135…
[.] copy       /etc/zsh/zprofile
```

For more sophisticated examples have a look at the [Examples](https://simple-automation.oddlama.org/en/latest/contents/examples.html) section in the
documentation.
