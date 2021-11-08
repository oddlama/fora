Trivia
======

.. contents::
    :local:

Variable precedence
-------------------

Global variables will be evaluated once at the start of the program:

#. Tasks will write their defaults to the global variables
#. Your :meth:`register_globals() <simple_automation.inventory.Inventory.register_globals>` will be called.

When a new context is created (to execute your :meth:`run() <simple_automation.inventory.Inventory.run>` function),
variables will be merged in the following order (lower entries overriding upper):

#. Globals
#. Groups in the order they have been added to the host
#. Host variables

Implicit templating variables
-----------------------------

.. topic:: Management reminder with ``simple_automation_managed``

    This implicit global variable expands to a message stating that a file is managed by simple automation.
    Just put a comment like ``# {{ simple_automation_managed }}`` in the first line of
    your templates to use it.

    Of course you can simply overwrite this in your globals or add your own
    variable if you want to customize the message.

.. topic:: Accessing the current host object directly from templates

    You can directly access the python manager / host object in templated environments.

    - ``context.manager`` will be the manager object.
    - ``context.host`` will be the host attached to the current context.

Tasks have an implicit enabled variable
---------------------------------------

Tasks have an implicit enabled variable. Often you need a variable to enable
or disable different tasks. Therefore, all tasks expose a variable called ``tasks.{identifier}.enabled``,
which by default is set to ``True``. The ``{identifier}`` is whatever has been choosen as the task identifier.

.. topic:: Example

    .. code-block:: python

        class MyInventory(Inventory):
            tasks = [MySimpleTask]

            def register_globals(self):
                # ...
                # Don't run MySimpleTask by default
                self.manager.set("tasks.my_simple_task.enabled", False)

            def register_inventory(self):
                # Do run the task only for hosts in the desktops group
                desktops = self.manager.add_group("desktops")
                desktops.set("tasks.my_simple_task.enabled", True)
                # ...

            def run(self, context):
                context.run_task(MySimpleTask)

Context remote execution defaults
---------------------------------

By default, when a task is run, the context's default values are set to the following (strict) values:

========== ========== ==========
Variable   Default    Description
========== ========== ==========
user       ``"root"`` User to execute commands as
umask      ``0o077``  File system umask value
dir_mode   ``0o700``  Permissions for directories created by :func:`directory() <simple_automation.transactions.basic.directory>` and alike.
file_mode  ``0o600``  Permissions for files created by :func:`copy() <simple_automation.transactions.basic.copy>`, :func:`template() <simple_automation.transactions.basic.template>` and alike.
owner      ``"root"`` File/directory owner
group      ``"root"`` File/directory group
========== ========== ==========

It is recommended to always specify these defaults at the beginning of your
task, so you know exactly what to expect.

Predefined transactions
-----------------------

See :ref:`api_transactions` for an overview of available transactions.

Executing only a part of the script
-----------------------------------

If you separate your inventory :meth:`run() <simple_automation.inventory.Inventory.run>` method
into several smaller methods, you will be able to run them individually. This
can be beneficial especially for large scripts.

You can select methods to execute by passing them as a comma separated list to
the ``--scripts`` command line option. They will be executed in order.
If not given, the parameter ``--scripts run`` is assumed.

A unified ``package()`` command for different distributions
-----------------------------------------------------------

If you manage hosts with different distributions, it might be beneficial to
create a wrapper around the ``package()`` transaction, which will chose the correct
one for your hosts. This is as simple as:

.. code-block:: python

    # When defining your inventory
    def register_inventory(self):
        distro_debian = self.manager.add_group("debians")
        distro_debian.set("system.distribution", "debian")

        distro_arch = self.manager.add_group("arch")
        distro_arch.set("system.distribution", "arch")

        # For all your hosts add them to the correct group
        my_host.add_group(distro_arch)

    # And define a global transaction wrapper
    def package(context, **kwargs):
        distro = context.vars.get("system.distribution")
        if distro == "arch":
            arch.package(**kwargs)
        elif distro == "debian":
            apt.package(**kwargs)

    # Now simply use package() in your tasks.

This approach is very flexible and would also allow you to e.g. add certain system
dependent paths to these group settings to make your tasks work on any distribution.

Check if a host belongs to a group
----------------------------------

.. code-block:: python

    def run(context):
        if self.my_host in self.some_group:
            # ...

        # Alternatively:
        if self.my_group in self.my_host.groups:
            # ...

Project to track dotfiles
-------------------------

You can simply create a single task that tracks all the locations you want
to backup. Occasionally run the script and all your paths will be checked into a git repository.

Where to store secrets
----------------------

Beware where and how you use secrets. If you have secrets, you should only ever store them
in a vault so they won't appear in your management repository! See :ref:`example_vaults` for information
on how to use vaults.

.. warning::

    Be careful, remote commands and their output may be printed in verbose or debugging modes!
    If you want to be certain that no secrets will ever be printed, only send them via ``input=...`` to the
    remote host in :meth:`remote_exec() <simple_automation.context.Context.remote_exec>`, or use them in files templated via :func:`template() <simple_automation.transactions.basic.template>`.

You can easily copy secrets from a vault into any variable storage by using
:meth:`copy() <simple_automation.vars.Vars.copy>`.

.. code-block:: python

    def register_inventory(self):
        # Copy into globals
        self.manager.copy("some_variable", self.vault)
        # Copy into group variables
        self.my_group.copy("some_variable", self.vault)
        # Copy into host variables
        self.my_host.copy("some_variable", self.vault)

Setting additional instance variables
-------------------------------------

There are two ways of associating additional information with a host:

.. code-block:: python

    # Accessed via {{ var }} in templated contexts
    self.my_host.set("var", "value")

.. code-block:: python

    # Accessed via {{ context.host.var }} in templated contexts
    self.my_host.var = "value"

Both are fine, while the first might be more flexible, as it will allow you to
inherit from global or group variables. You can use both approaches to
access to arbitrary python objects from templated contexts, by using any object as the value.

Relative local paths
--------------------

Local files given by ``src=`` in :func:`copy() <simple_automation.transactions.basic.copy>` or :func:`template() <simple_automation.transactions.basic.template>`
are relative to the project path where your main executable resides. You can override that behavior
by passing a ``main_directory`` to :func:`run_inventory() <simple_automation.manager.run_inventory>`.

Asking only once for a vault key for multiple vaults
----------------------------------------------------

You can either use a keyfile, or ask yourself for the password before running your inventory:

.. code-block:: python

    from simple_automation import Inventory, SymmetricVault, run_inventory
    import getpass

    global_key = None

    # -------- Define your inventory --------
    class MyInventory(Inventory):
        # ...
        def register_vaults(self):
            self.vault1 = self.manager.add_vault(SymmetricVault, file="vault1.asc", key=global_key)
            self.vault2 = self.manager.add_vault(SymmetricVault, file="vault2.asc", key=global_key)

    # -------- Run the inventory --------
    if __name__ == "__main__":
        global_key = getpass("Shared vault key: ")
        run_inventory(MyInventory)

.. warning::

    The downside of this approach is that you will have to unlock your vault every time,
    even when you would for example edit any unrelated other vault.
