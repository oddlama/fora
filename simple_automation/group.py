"""
Provides api for group definitions.
"""

from typing import cast

# TODO make Example a section in the sphinx documentation
class GroupType(MockupType):
    """
    A mockup type for group modules. This is not the actual type of an instanciated
    module, but will reflect some of it's properties better than ModuleType.

    This class also represents all meta information available to a group module when itself
    is being loaded. It allows a module to access and modify its associated meta-information.
    After the module has been loaded, the meta information will be transferred directly to the module.

    When writing a group module, you can simply import :attr:`simple_automation.group.this`,
    which exposes an API to access/modify this information.

    Example: Using meta information (groups/webserver.py)

    .. code-block:: python

        from simple_automation.group import this

        # Require that the 'servers' groups is processed before this group when resolving
        # variables for a host at execution time. This is important to avoid variable
        # definition ambiguity (which would be detected and reported as an error).
        this.after("server")
    """

    reserved_vars: set[str] = set(["module", "name", "loaded_from", "groups_before", "groups_after"])
    """
    A list of variable names that are reserved and must not be set by the module.
    """

    def __init__(self, name: str, loaded_from: str):
        self.module: ModuleType
        """
        The associated dynamically loaded module (will be set before the dynamic module is executed).
        """

        self.name: str = name
        """
        The name of the group. Must not be changed.
        """

        self.loaded_from: str = loaded_from
        """
        The original file path of the instanciated module.
        """

        self.groups_before: set[str] = set()
        """
        This group will be loaded before this set of other groups.
        """

        self.groups_after: set[str] = set()
        """
        This group will be loaded after this set of other groups.
        """

    @transfer
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
            raise ValueError("Cannot add reverse-dependency to self!")

        self.groups_before.add(group)

    @transfer
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

    @transfer
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
            raise ValueError("Cannot add dependency to self!")

        self.groups_after.add(group)

    @transfer
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

    @staticmethod
    def get_variables(group: GroupType) -> set[str]:
        """
        Returns the list of all user-defined attributes for a group.

        Parameters
        ----------
        group : GroupType
            The group module

        Returns
        -------
        set[str]
            The user-defined attributes for the given group
        """
        return _get_variables(GroupType, group)

this: GroupType = cast(GroupType, None) # Cast None to ease typechecking in user code.
"""
This variable holds all meta information available to a group module when
it is being loaded. It must not be used anywhere else but inside the
definition (source) of the actual module.
"""
