.. _architecture:

Architecture
============

In this document you will find a high-level overview of the library architecture.

.. code-block::

   ┌─────────┐ Gets variables     ┌─────────┐         Initializes  ┌───────────┐
   │ Context │ ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌→ │ Manager │ ←——————————————————— │ Inventory │
   └─────────┘                    └─────────┘                      └───────────┘
        ┊ SSH connection to            │ Owns                            ┊ Uses tasks to build
        ┊ a specific host              │       ┌──────┐                  ┊ global script
        └╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ │ ╌╌→ ┌──────┐ │  ←╌┐             ┊
                                       ├───→ │ Host │ ┘    ┊             ┊
                                       │     └──────┘      ┊             ┊
                                       │                   ┊             ┊
                                       │       ┌───────┐   ┊             ┊
                                       │     ┌───────┐ │ ╌╌┘             ┊
                                       ├───→ │ Group │ ┘ Contains        ┊
                                       │     └───────┘                   ┊
                                       │                                 ┊
                                       │       ┌──────┐                  ┊
                                       │     ┌──────┐ │ ←╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┘
                                       ├───→ │ Task │ ┘ ─────────────────┐
                                       │     └──────┘    Built from many │
                                       │                                 ↓
                                       │       ┌───────┐            ┌─────────────┐
                                       │     ┌───────┐ │          ┌─────────────┐ │
                                       └───→ │ Vault │ ┘          │ Transaction │ ┘
                                             └───────┘            └─────────────┘

Program start
-------------

1. A manager (and your inventory) is instanciated
2. Command line options are parsed
3. register_vaults is called
4. register_globals is called
5. register_inventory is called
6. The given entry function (run(context) by default) is called

Class functionality
-------------------

Inventory
^^^^^^^^^
- "Builder" for the inventory + defines tasks to be run
- Registers hosts, tasks, groups and vaults
- Defines the actions to be done on the hosts

Host
^^^^

- Represents a single host
- Stores host specific variables

Group
^^^^^

- Represents a group of hosts
- Stores variables that are shared between all belonging hosts

Vault
^^^^^

- Permanent encrypted storage for variables
- Useful to safely store and use secrets
- Can be checked into a git repository

Manager
^^^^^^^
- Initialized based on a passed inventory, which is called to build the inventory.
- Stores (i.e. owns) hosts, groups, tasks, vaults
- Provides CLI commands

Context
^^^^^^^
- Encapsulates an ssh connection to a specific host, and allows easy remote execution.
- Stores the actual processed set of variables defined for a host (merging globals and group variables)
- Stores intermediate data while the script is executed for a specific host

Task
^^^^
- A collection of transactions and logic that achieves a bigger goal. (e.g. Install and configure zsh.)
- Can define and use variables, which allow easy per-host or per-group customization.

TrackedTask
^^^^^^^^^^^
- An extended task which will track a defined set of directories and files
  in a git repository, after it has finished execution.

Transaction function
^^^^^^^^^^^^^^^^^^^^

- A single action that can be done on a remote host. (e.g. install package, template and upload file, create directory with given permissions, ...)
- A function that can be called inside a task to change remote state
- Examines current state
- Defines target state
- If changes are necessary, performs these changes on the remote
- Returns an object that stores information about what has been changed.
