"""
Provides the Inventory class.
"""

class Inventory:
    """
    An inventory is a collection of definitions for vaults, tasks, global variables, hosts and groups.
    It also defines what tasks are run for each host.
    """

    tasks = []
    """
    A list of task classes that should be registered to this inventory.
    """

    def __init__(self, manager):
        self.manager = manager

    def register_vaults(self):
        """
        This function will be executed when your inventory should define
        the vaults it want's to access. Do this via a call to :meth:`self.manager.add_vault() <simple_automation.manager.Manager.add_vault>`.
        Also remember to save the return value of this function, which will be
        a vault object you can later use to access stored values.
        """
        pass

    def register_tasks(self):
        """
        This function will be executed when your inventory should define
        the tasks it want's to run. By default, this function will register
        all tasks given in the list self.tasks.

        You can register tasks manually via a call to :meth:`self.manager.add_task() <simple_automation.manager.Manager.add_task>`.
        You may either save the return value of this function, and use ret.exec(context)
        to execute the task, or use the convenience method context.run_task(TaskClass).
        """
        for task_cls in self.tasks:
            self.manager.add_task(task_cls)

    def register_globals(self):
        """
        This function will be executed when your inventory should define
        its global variables. Use :meth:`self.manager.set() <simple_automation.manager.Manager.set>` to define them.
        """
        pass

    def register_inventory(self):
        """
        This function will be executed when your inventory should define
        the hosts and groups. Use :meth:`self.manager.add_host() <simple_automation.manager.Manager.add_host>` and :meth:`self.manager.add_group() <simple_automation.manager.Manager.add_group>`
        to define them.
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def run(self, context):
        """
        This function will be executed for each host context,
        and is your main customization point. Here you can build
        your logic of what tasks to execute for a given host.
        """
        raise NotImplementedError("Must be overwritten by subclass.")
