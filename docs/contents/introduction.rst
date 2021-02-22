.. _introduction:

Introduction
============

Simple automation is an ansible-inspired infrastructure and configuration management tool,
but with a focus on minimalism and simplicity. Its intended uses are small-scale machine administation, system configuration tracking,
or even just dotfiles management. Although it can certainly be used to administer bigger
infrastructures.

.. hint::

    If you want a high level overview of the different library components
    and how they work together, please have a look at the :ref:`architecture` page.

Here is an example of how to use simple automation to manage some global config files.

.. code-block:: python

    from simple_automation import run_inventory, Inventory, Task
    from simple_automation.transactions.basic import copy, directory

    # -------- Define a task --------
    class TaskZsh(Task):
        identifier = "zsh"
        description = "Installs global zsh configuration"

        def run(self, context):
            # Execute as root and set permission defaults
            context.defaults(user="root", umask=0o022, dir_mode=0o755, file_mode=0o644,
                             owner="root", group="root")

            # Copy configuration
            directory(context, path="/etc/zsh")
            copy(context, src="files/zsh/zshrc", dst="/etc/zsh/zshrc")
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


Feature Overview
----------------

- Use python to write your configuration and don't be limited by a domain specific language.
- Supports encrypted variable storage.
- Executes all commands over a single ssh connection per host (→ fast execution)
- Concicse, readable output (optionally verbose but still quite compact)
- Tracking of arbitrary files and folders in a git repository. Allows you to easily keep track of your system's state over time.


Focus on minimalism and simplicity
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    This library has a very specific purpose: Conveniently make it possible
    to alter the state of remote hosts by executing commands over
    an SSH connection. We don't want to increase complexity by introducing
    niche features. We will provide everything that is necessary to get there,
    plus some convenience features that most users need (e.g. vaults).
    Because this library is small, you will be capable of building the rest yourself,
    if you require more.

    The whole implementation of this library has just under 1300 LoC.
    Additionally, it has very few dependencies:

    - jinja2 for templating
    - pycryptodome for symmetrically encrypted vaults (scrypt + AES-256-GCM; library not required if feature not used).

.. warning::

    Currently there is no supported way to become a privileged user on a host, when logging in as a unprivileged user.
    If you want to do things as root or an arbitrary user on a remote host,
    you will need to login as root.

Installation
------------

Use can use pip to install simple_automation. If you want to help maintaining a package
for your favourite distribution, feel free to reach out.

.. topic:: Using pip

    .. code-block:: bash

        pip install simple_automation

.. hint::

    Have a look at :ref:`basic-project-setup` for an overview of how to setup
    a new inventory.
