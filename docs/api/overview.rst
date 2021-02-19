.. _api:

Overview
========

The :class:`Manager <simple_automation.manager.Manager>` and :class:`Context <simple_automation.context.Context>` are two
of the main classes you will interact with. The Manager is used to register your inventory and the context is
used to execute commands on remote hosts.

.. autosummary::
    simple_automation.manager.Manager
    simple_automation.context.Context

The following classes are instanciated by registering things in your inventory
and are also used regularly. The most important classes are the :class:`Task <simple_automation.task.Task>` and
:class:`TrackedTask <simple_automation.task.TrackedTask>` from which you can derive your own tasks.

.. autosummary::
    simple_automation.inventory.Inventory
    simple_automation.host.Host
    simple_automation.group.Group
    simple_automation.task.Task
    simple_automation.task.TrackedTask
    simple_automation.vault.GpgVault
    simple_automation.vault.SymmetricVault
