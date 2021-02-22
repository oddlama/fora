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
    │   └── zsh/            -- (Sorted by task)
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
        from simple_automation import run_inventory, Inventory
        from tasks.my_simple_task import MySimpleTask

        # -------- Define your inventory --------
        class MyInventory(Inventory):
            tasks = [MySimpleTask]

            def register_inventory(self):
                self.manager.add_host("my_home_pc", ssh_host="root@localhost")

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
            identifier = "my_task"
            description = "Just copies some files"

            def run(self, context):
                # Execute as root and set permission defaults
                context.defaults(user="root", umask=0o022, dir_mode=0o755, file_mode=0o644,
                                 owner="root", group="root")

                # Create a directory and copy some files
                directory(context, path="/etc/zsh")
                copy(context, src="files/zsh/zshrc", dst="/etc/zsh/zshrc")
                copy(context, src="files/zsh/zprofile", dst="/etc/zsh/zprofile")

.. warning::

    You should always set your desired defaults at the beginning of a task,
    so there will be no surprises later on. Be as strict as possible. If you
    don't set your own defaults, the task will use ``user='root', umask=0o077, dir_mode=0o700, file_mode=0o600, owner='root', group='root'``.

Task specific variables
-----------------------

You can define variables for your tasks, which you can use to
customize e.g. installation paths, or to conditionally enable
certain functionality. In :meth:`set_defaults() <simple_automation.task.Task.set_defaults>` you
can define what default values your variables should have, if they are not
overwritten by any globals, group variables or host variables.

.. hint::

    All tasks automatically expose a variable named ``tasks.{identifier}.enabled``,
    which you can use to conditionally disable a whole task.

Example:

.. code-block:: python

    from simple_automation import Task
    from simple_automation.transactions.basic import copy, directory

    class MyTask(Task):
        identifier = "my_task"
        description = "A short description"

        def set_defaults(self):
            self.manager.set(f"tasks.{identifier}.config_folder", "/etc/zsh")

        def run(self, context):
            # Use variables in templated parameters:
            template(context, src="templates/zsh/zshrc.j2", dst="{{ tasks.zsh.config_folder }}/zshrc")

            # Use variables as a conditional
            if context.vars.get("tasks.zsh.some_boolean"):
                # ...

Global variables
----------------

Conditional transactions
------------------------

Tracking files
--------------

Groups
------

Vaults
------
