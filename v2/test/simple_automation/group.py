from typing import Optional

import simple_automation

class GroupMeta:
    """
    This class represents all meta information available to a group module when itself is being loaded.
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

        self.groups_before: set[str] = set()
        self.groups_after: set[str] = set()

    def before(self, group: str):
        """
        Adds a reverse-dependency on the given group.

        Parameters
        ----------
        group : str
            The group that must be loaded before this group.
        """
        if group not in simple_automation.available_groups:
            raise ValueError(f"Referenced invalid group '{group}'!")
        if group == self.name:
            raise ValueError(f"Cannot add reverse-dependency to self!")

        self.groups_before.add(group)

    def before_all(self, groups: list[str]):
        """
        Adds a reverse-dependency on all given groups.

        Parameters
        ----------
        groups : list[str]
            The groups
        """
        for g in groups:
            self.before(g)

    def after(self, group: str):
        """
        Adds a dependency on the given group.

        Parameters
        ----------
        group : str
            The group that must be loaded after this group.
        """
        if group not in simple_automation.available_groups:
            raise ValueError(f"Referenced invalid group '{group}'!")
        if group == self.name:
            raise ValueError(f"Cannot add dependency to self!")

        self.groups_after.add(group)

    def after_all(self, groups: list[str]):
        """
        Adds a dependency on all given groups.

        Parameters
        ----------
        groups : list[str]
            The groups
        """
        for g in groups:
            self.after(g)

this: Optional[GroupMeta] = None
"""
This variable holds all meta information available to a group module when itself is being loaded.
This variable should only ever be used in the context of a group module as shown below, otherwise
it will be None.

It allows the module to access and supply meta-information about itself, such as
dependencies on other groups.

When writing a group module, you can simply import :attr:`simple_automation.group.this`,
which exposes an API to access/modify this information.

.. topic:: Example: Using meta information (groups/webserver.py)

    .. code-block:: python

        from simple_automation.group import this

        # Require that the 'servers' groups is processed before this group when resolving
        # variables for a host at execution time. This is important to avoid variable
        # definition ambiguity (which would be detected and reported as an error).
        this.after("server")
"""
