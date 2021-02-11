
class Inventory:
    """
    An inventory is a collection of definitions for vaults, tasks, global variables, hosts and groups.
    It also defines what tasks are run for each host.
    """

    def __init__(self, manager):
        self.manager = manager

    def register_vaults(self):
        """
        This function will be executed when your inventory should define
        the vaults it want's to access. Do this via a call to self.manager.add_vault().
        Also remember to save the return value of this function, which will be
        a vault object you can later use to access stored values.
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def register_tasks(self):
        """
        This function will be executed when your inventory should define
        the tasks it want's to run. Do this via a call to self.manager.add_task().
        You can either save the return value of this function, and use ret.exec(context)
        to execute the task, or use the convenience method context.run_task(TaskClass).
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def register_globals(self):
        """
        This function will be executed when your inventory should define
        its global variables. Use self.manager.set() to define them.
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def register_inventory(self):
        """
        This function will be executed when your inventory should define
        the hosts and groups. Use self.manager.add_host() and self.manager.add_group()
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
