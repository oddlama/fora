Examples
========

In the following we will show some examples of how to use simple_automation.

.. _basic-project-setup:

Setting up a basic project
--------------------------

Typically, a project has a structure similar to the following:

.. code-block::

    my_project/
    ├── templates/          -- File templates
    │   └── zsh/            -- (Best sorted by task)
    │       └── zshrc.j2
    ├── tasks/              -- Task definitions
    │   ├── __init__.py
    │   └── zsh.py
    ├── myvault.asc         -- (Optional) Encrypted variable storage
    └── site.py*            -- Your inventory and main executable


You will mainly have to deal with template files, task definitions and maintaining your inventory script.
``site.py`` is your main executable, and is the place where you will define your inventory,
and where you will find the main execution routine.

.. topic:: site.py

    .. code-block:: python

        #!/usr/bin/env python3
        from simple_automation import run_inventory, Inventory, SymmetricVault
        from tasks.my_simple_task import MySimpleTask

        # -------- Define your inventory --------
        class MyInventory(Inventory):
            tasks = [MySimpleTask]

            # (Optional) Vaults store encrypted variables
            def register_vaults(self):
                # -------- Load vault --------
                self.vault = self.manager.add_vault(SymmetricVault, file="myvault.asc")

            # (Optional) Global variables
            def register_globals(self):
                # -------- Set global variables --------
                self.manager.set("tasks.my_simple_task.enabled", False)

            def register_inventory(self):
                # -------- Define Groups --------
                desktops = self.manager.add_group("desktops")
                desktops.set("system.is_desktop", True)
                desktops.copy("system.root_pw", self.vault)

                # -------- Define Hosts --------
                my_home_pc = self.manager.add_host("my_home_pc", ssh_host="root@localhost")
                my_laptop.add_group(desktops)

            def run(self, context):
                context.run_task(MySimpleTask)

        # -------- Run the inventory --------
        if __name__ == "__main__":
            run_inventory(MyInventory)

Defining a task
---------------

To create a new task, start by inheriting from :class:`simple_automation.task.Task`.
You need to specify an identifier for your task, which will for example be used
for related variables. The description will be printed in verbose mode.

.. topic:: tasks/my_simple_task.py

    .. code-block:: python

        from simple_automation import Task
        from simple_automation.transactions.basic import copy, directory

        # -------- Define a task --------
        class MySimpleTask(Task):
            identifier = "mytask"
            description = "Just copies some files"

            def run(self, context):
                # Change permission defaults
                with context.defaults(umask=0o022, dir_mode=0o755, file_mode=0o644):
                    # Create a directory and copy some files
                    directory(context, path="/etc/zsh")
                    copy(context, src="files/zsh/zshrc", dst="/etc/zsh/zshrc")
                    copy(context, src="files/zsh/zprofile", dst="/etc/zsh/zprofile")

.. hint::

    Default for user, umask, file/dir modes, file owner/group are strict by default.
    If not changed explicitly as shown above, the task will use ``user='root', umask=0o077, dir_mode=0o700, file_mode=0o600, owner='root', group='root'``.

Task specific variables
-----------------------

You can define variables for your tasks, which you can use to
customize e.g. installation paths, or to conditionally enable
certain functionality. In :meth:`set_defaults() <simple_automation.task.Task.set_defaults>` you
can define what default values your variables should have, if they are not
overwritten by any globals, group variables or host variables.

Each task has an identifier. If you always use this identifier as part of your variable name,
you can avoid clashes with other task variables.

.. hint::

    All tasks automatically expose a variable named ``tasks.{identifier}.enabled``,
    which you can use to conditionally disable a whole task.

.. rubric:: Example:

.. code-block:: python

    from simple_automation import Task
    from simple_automation.transactions.basic import template

    class MyTask(Task):
        identifier = "mytask"
        description = "A short description"

        def set_defaults(self):
            self.manager.set(f"tasks.{self.identifier}.config_folder", "/etc/mytask")

        def run(self, context):
            # Use variables in templated parameters:
            template(context, src="templates/mytask/template.j2", dst="{{ tasks.mytask.config_folder }}/config")

            # Use variables as a conditional
            if context.vars.get("tasks.mytask.some_boolean"):
                # ...

.. rubric:: templates/mytask/template.j2

.. code-block::

    # This file's path is {{ tasks.mytask.config_folder }}/config
    # and is saved on host {{ context.host.identifier }}

Global variables
----------------

You can set global variables by calling :meth:`self.manager.set() <simple_automation.manager.Managert.set>`.
This is mainly helpful if you want to create customization points for your
own global inventory :meth:`run() <simple_automation.inventory.Inventory.run>` routine.

.. code-block:: python

    from simple_automation import Inventory

    class MyInventory(Inventory):
        # ...
        def register_globals(self):
            # -------- Set global variables --------
            self.manager.set("install_dotfiles", False)

        def run(self, context):
            if context.vars.get("install_dotfiles"):
                # ...

Groups
------

If you have multiple hosts with related configuration needs,
you can add them to groups to manage this common functionality.
You might for example want to add all desktop machines into one group
to install common software that you need on all of those hosts.

.. code-block:: python

    from simple_automation import Inventory

    class MyInventory(Inventory):
        # ...

        def register_inventory(self):
            # -------- Define Groups --------
            self.desktops = self.manager.add_group("desktops")
            self.desktops.set("system.is_desktop", True)

            # -------- Define Hosts --------
            my_home_pc = self.manager.add_host("my_home_pc", ssh_host="root@localhost")
            my_home_pc.add_group(self.desktops)

        def run(self, context):
            # ...

            # Check if the current host belongs to a group
            if context.host in self.desktops:
                pass

            # Or examine a variable you set for that group
            if context.vars.get("system.is_desktop"):
                pass


Using transaction results
-------------------------

Sometimes you will need results from past transactions to determine what to do next.
For example you might need to run some transactions only if a directory was created.

All transaction return an object of type :class:`CompletedTransaction <simple_automation.transaction.CompletedTransaction>`
which you can use to examine the initial and final transaction state.

.. topic:: Conditional execution based on directory creation state

    .. code-block:: python

        from simple_automation import Task
        from simple_automation.transactions.basic import directory

        class MyTask(Task):
            # ...
            def run(self, context):
                # ...
                res = directory("/some/directory")
                if not res.initial_state["exists"]:
                    # Directory didn't exist before
                    # Do some additional work

Conditional execution based on command output
---------------------------------------------

You might find yourself in the situation where you need the
output of an arbitrary command, or a file on the remote system
to determine the next steps. This can be done by directly
executing a command on the remote system via the given context.

.. hint::

    The method :meth:`context.remote_exec() <simple_automation.context.Context.remote_exec>` works
    similar to ``subprocess.run()``, but is executed on the remote host. Please view the method documentation
    to see which parameters are avaiable.

.. topic:: Executing a remote command

    .. code-block:: python

        from simple_automation import Task

        class MyTask(Task):
            # ...
            def run(self, context):
                # ...
                remote_content = context.remote_exec(["cat", "/path/to/some/file"], checked=True)
                content = remote_content.stdout
                # Use the content in your logic.

Tracking files
--------------

You can have tasks automatically check some files or directories into a git repository,
so you can keep track of your system's state over time. This is as simple as
deriving from :class:`TrackedTask <simple_automation.task.TrackedTask>` instead of :class:`Task <simple_automation.task.Task>`,
and defining some additional class variables. Be sure to have a look at the documentation of :class:`TrackedTask <simple_automation.task.TrackedTask>` to see
which options are available.

.. warning::

    Your chosen tracking repository should already have at least one commit.
    This is necessary because only then there will be a tracked branch when
    checking it out initially.

.. hint::

    It may be beneficial to create your own base class for all tracked
    tasks, to set a common tracking repository. You will then only have to
    add all files and directories you want to track to :attr:`tracking_paths <simple_automation.task.TrackedTask.tracking_paths>`
    in the actual task.

.. topic:: Define a common base task

    .. code-block:: python

        from simple_automation import TrackedTask

        class MyTrackedTask(TrackedTask):
            # Save the url into a vault so it doesn't leak into your management repository
            tracking_repo_url = "{{ tracking.repo_url }}"
            # Choose some path where the actual tracking repository will be cloned on your machines
            tracking_local_dst = "/var/lib/root/tracking"

.. topic:: Track some files

    Simply extend any of your task by inheriting from your new base task,
    then set the files and/or directories you want to track.

    .. code-block:: python

        class TaskZshConfig(MyTrackedTask):
            tracking_paths = ["/etc/zsh"]
            # ...

.. topic:: A tracking-only task

    It is perfectly valid to create a new task that does nothing but
    track some files.

    .. code-block:: python

        class TaskTrackSomething(MyTrackedTask):
            identifier = "track_something"
            description = "Tracks something"
            tracking_paths = ["/etc/location1", "/var/lib/something_else"]

.. topic:: Track arbitrary information

    You can also track arbitrary information, by querying this information in your
    tasks :meth:`run() <simple_automation.task.Task.run>` function and save it into
    a temporary destination.

    .. code-block:: python

        # Track installed packages from portage
        class TaskTrackInstalledPackages(MyTrackedTask):
            identifier = "track_installed_packages"
            description = "Tracks all installed packages"
            tracking_paths = ["/var/lib/root/installed_packages"]

            def run(self, context):
                # Change the command to fit your package manager
                save_output(context, command=["qlist", "-CIv"],
                            dst="/var/lib/root/installed_packages",
                            desc="Query installed packages")

.. _example_vaults:

Vaults
------

Vaults let you store variables in an encrypted file. This is useful
when you want to safely store secrets in your management repository. By default
we offer symmetrically encrypted vaults (scrypt+AES-256-GCM), or gpg encrypted vaults (convenient
in combination with a smartcard or YubiKey).

For specific information on each, have a look at the respective class documentations:

- :class:`SymmetricVault <simple_automation.vault.SymmetricVault>`
- :class:`GpgVault <simple_automation.vault.GpgVault>`

A vault is just a variable storage, and therefore works similar to other variable storages
like groups or hosts.

.. topic:: Creating/Editing a vault

    If you have defined a vault, you can use ``./site.py --edit-vault <vault_file>`` to edit it.
    This will open ``$EDITOR`` and show the vault content in JSON format.

.. topic:: Using a vault

    .. code-block:: python

        #!/usr/bin/env python3
        from simple_automation import Inventory, SymmetricVault
        from tasks.my_simple_task import MySimpleTask

        # -------- Define your inventory --------
        class MyInventory(Inventory):
            # ...
            def register_vaults(self):
                # You can optionally pass the unlock key / keyfile if needed
                self.vault = self.manager.add_vault(SymmetricVault, file="myvault.asc")
                # You may define multiple vaults. Store them in your instance to access them later.

            def register_inventory(self):
                # ...
                # Copy root password from vault
                my_laptop.copy("system.root_pw", self.vault)

.. topic:: Creating a GpgVault

    .. code-block:: python

        # ...
        def register_vaults(self):
            self.vault = self.manager.add_vault(GpgVault, file="myvault.gpg", recipient="your_keyid")

.. hint::

    Use :meth:`copy() <simple_automation.vars.Vars.copy>` to easily copy a variable from
    a vault into your globals, group or host variables.
