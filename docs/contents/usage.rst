.. _usage:

Usage
=====

Welcome to the usage section! Below is a table of contents for this
guide. Feel free to directly jump to the topic of your interest.

.. contents::
    :local:


Installation
------------

Use can use pip to install simple_automation, or run from source:

.. topic:: Using pip

    .. code-block:: bash

        pip install simple_automation

.. topic:: Setting up the basic project

    You can make use of simple_automation by simply importing it in a python script.
    First, you will define your inventory and your tasks, and secondly define an execution routine.
    TODO INCLUDE FROM FILE!

    .. code-block:: python

        #!/usr/bin/env python3
        from simple_automation import run_inventory, Inventory

        class MyInventory(Inventory):
            def register_tasks(self):
                self.manager.add_task(TaskZsh)

            def register_globals(self):
                pass

            def register_inventory(self):
                self.manager.add_host("my_laptop", ssh_host="root@localhost")

            def run(self, context):
                context.run_task(TaskZsh)

        # -------- Run the inventory --------
        if __name__ == "__main__":
            run_inventory(MyInventory)

Basic invokation
----------------

TODO
