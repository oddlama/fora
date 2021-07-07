"""
This module provides all task related functionality, as well as a global
variable 'this' that may be used inside a task module to modify it's own meta
information.
"""

from types import ModuleType
from typing import Optional

from .types import TaskType

class TaskMeta:
    """
    This class represents all meta information available to a task module when itself is being loaded.
    It allows a module to access and modify its associated meta-information.
    """

    def __init__(self, name: str, loaded_from: str):
        self.name: str = name
        """
        The name of the group. Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

    @staticmethod
    def get_variables(task: TaskType) -> set[str]:
        """
        Returns the list of all user-defined attributes for a task.

        Parameters
        ----------
        task : TaskType
            The task module

        Returns
        -------
        set[str]
            The user-defined attributes for the given task
        """
        task_vars = set(attr for attr in dir(task) if
                         not callable(getattr(task, attr)) and
                         not attr.startswith("_") and
                         not isinstance(getattr(task, attr), ModuleType))
        task_vars -= TaskType.reserved_vars
        task_vars.remove('this')
        return task_vars

this: Optional[TaskMeta] = None
"""
This variable holds all meta information available to a task module when itself is being loaded.
This variable should only ever be used in the context of a task module as shown below, otherwise
it will be None.

It allows the module to access meta-variables about itself, such as the task's id
that has been used to instanciate it in the inventory. It also allows modification of these
meta properties, such as it's description.

When writing a task module, you can simply import :attr:`simple_automation.task.this`,
which exposes an API to access/modify this information.

.. topic:: Example: Using meta information (tasks/mytask.py)

    .. code-block:: python

        from simple_automation.task import this

        # The task id used for instanciation as defined in the inventory
        print(this.id)

        # Set the ssh task (useful if it differs from the id)
        this.ssh_task = "root@localtask"

        # Add the task to a group
        this.add_group("desktops")
"""
