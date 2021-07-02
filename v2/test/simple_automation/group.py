from typing import Optional

class GroupMeta:
    """
    This class represents all meta information available to a group module when itself is being loaded.
    It allows a module to access and modify its associated meta-information.
    """

    def __init__(self, name, loaded_from):
        self.name = name
        self.loaded_from = loaded_from

        self.groups_before = set()
        self.groups_after = set()

    def before(self, group):
        self.groups_before.add(group)

    def before_all(self, groups):
        self.groups_before.update(groups)

    def after(self, group):
        self.groups_after.add(group)

    def after_all(self, groups):
        self.groups_after.update(groups)

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
