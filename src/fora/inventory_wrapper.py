from __future__ import annotations

import os
from dataclasses import dataclass, field
from glob import glob
from typing import Any, Optional, Union

from fora.types import ModuleWrapper

@dataclass
class HostDeclaration:
    """A declaration of a host in an inventory."""

    url: str
    """
    The default url used to connect to this host. If this is given without an connection
    schema (like `ssh://`), `ssh://` will be used as the default. The function responsible
    for this is `qualify_url`.
    """

    name: Optional[str] = None
    """
    The name that will be used to refer to this specific host.

    If this is `None`, the name is extracted from the `url` after
    qualification by the means of `extract_hostname`. In that case, the connector
    determined by the `url` is responsible to parse it and provides a hostname.
    This means that both of the urls `localhost` and `ssh://root@localhost:22` will
    result in a host named `localhost` by default.

    Beware that hostname extraction naturally needs to occurr before the corresponding
    host module is loaded. The module can theoretically overwrite its intially assigned
    `url` or even specify an explicit connector implementation, which can never be used
    to assign a different name to the host in retrospect. Therefore, specifying the final
    `url` in the inventory is preferred.
    """

    file: Optional[str] = None
    """
    The module file for this host, relative to the `base_dir`.

    If `None`, this will default to `{hosts_dir}/{name}.py`. In that case,
    the file is optional and will only be loaded when it exists.
    If this attribute is set explicitly the file must exist, otherwise an error will be thrown.
    """

    groups: list[str] = field(default_factory=list)
    """
    The groups for this host. Duplicate entries are ignored.
    All hosts will always be added to the global `all` group,
    regardless of whether it is part of this list.
    """

@dataclass
class GroupDeclaration:
    """A declaration of a group in an inventory."""

    name: str
    """The name that will be used to refer to this specific group."""

    file: Optional[str] = None
    """
    The module file for this group, relative to the `base_dir`.

    If `None`, this will default to `{groups_dir}/{name}.py`. In that case,
    the file is optional and will only be loaded when it exists.
    If this attribute is set explicitly the file must exist, otherwise an error will be thrown.
    """

    after: list[str] = field(default_factory=list)
    """
    This group will be loaded _after_ this given list of groups.
    The global `all` group will always be added to this list.
    Duplicates are ignored.
    """

    before: list[str] = field(default_factory=list)
    """
    This group will be loaded _before_ this given list of groups.
    Duplicates are ignored.
    """

@dataclass
class InventoryWrapper(ModuleWrapper):
    """
    A wrapper class for inventory modules. This will wrap any instanciated
    inventory to provide default attributes and methods for the inventory.
    """

    groups_dir: str = "groups"
    """The directory where to search for group module files, relative to the inventory."""

    hosts_dir: str = "hosts"
    """The directory where to search for host module files, relative to the inventory."""

    hosts: list[Union[str, HostDeclaration, dict[str, Any]]] = field(default_factory=list)
    """
    The list of hosts in this inventory. See `HostDeclaration` for an explanation
    of the parameters for individual hosts. If a `dict` is given, it is automatically
    used to construct a HostDeclaration. Providing a single `str` is equivalent to
    `HostDeclaration(url=the_str)`.

    Duplicate entries (same name) will cause an exception to be raised when the
    inventory is loaded.

    Example:

        hosts = [HostDeclaration(url="localhost", groups=["desktops"])),
                 dict(url="host.example.com", name="myhost"),
                 "example.com"]
    """

    groups: Optional[list[Union[str, GroupDeclaration, dict[str, Any]]]] = None
    """
    The list of groups in this inventory. See `GroupDeclaration` for an explanation
    of the parameters for individual groups. If a `dict` is given, it is automatically
    used to construct a GroupDeclaration. Providing a single `str` is equivalent to
    `GroupDeclaration(name=the_str)`.

    The global `all` group will always be added to this list, if it isn't already.

    Duplicate entries (same name) will cause an exception to be raised when the
    inventory is loaded.

    Example:

        groups = [GroupDeclaration(name="desktops", after=["archlinux"]),
                  dict(name="servers", after=["archlinux"]),
                  "archlinux"]
    """

    _topological_order: list[str] = field(default_factory=list)
    """
    A topological order of all groups in this inventory. Will be filled
    when the inventory is loaded.
    """

    def global_variables(self) -> dict[str, Any]:
        """
        Returns a list of global variables to implicitly add to the global `all` group
        (before it is actually loaded). Useful to provide global per-inventory
        variables.

        Returns
        -------
        dict[str, Any]
            Global variables for this inventory
        """
        return dict()

    def available_groups(self) -> set[str]:
        """
        Returns the set of available groups in this inventory.
        By default each module file in `groups_dir` (relative to the inventory module)
        creates a group of the same name, disregarding the `.py` extension.

        Note that the `all` group will always be made available, even if it isn't explicitly
        returned by this function. This function should only return groups that have a
        corresponding module file.

        Returns
        -------
        set[str]
            The available group definitions.
        """
        # Find group files relative to the inventory module
        if self.module is None or self.module.__file__ is None:
            raise RuntimeError("Cannot return base directory for an inventory module without an associated module file.")

        group_files_glob = os.path.join(os.path.dirname(self.module.__file__), self.groups_dir, "*.py")
        return set(os.path.splitext(os.path.basename(file))[0] for file in glob(group_files_glob))

    def base_dir(self) -> str:
        """
        Returns absolute path of this inventory's base directory, which
        is usually its containing folder.

        Raises
        ------
        RuntimeError
            If the inventory has no associated module file.

        Returns
        -------
        str
            The absolute base directory path.
        """
        if self.module is None or self.module.__file__ is None:
            raise RuntimeError("Cannot return base directory for an inventory module without an associated module file.")
        return os.path.realpath(os.path.dirname(self.module.__file__))

    def group_module_file(self, name: str) -> Optional[str]:
        """
        Returns the absolute group module file path given the group's name.
        Returning None associates no group module file to the group by default.

        Parameters
        ----------
        name
            The group name to return the module file path for.

        Returns
        -------
        Optional[str]
            The group module file path.
        """
        return os.path.join(self.base_dir(), self.groups_dir, f"{name}.py")

    def host_module_file(self, name: str) -> Optional[str]:
        """
        Returns the absolute host module file path given the host's name.
        Returning None associates no host module file to the host by default.

        Parameters
        ----------
        name
            The host name to return the module file path for.

        Returns
        -------
        Optional[str]
            The host module file path.
        """
        return os.path.join(self.base_dir(), self.hosts_dir, f"{name}.py")

    def qualify_url(self, url: str) -> str:
        """
        Returns a valid url for any given url from the hosts array if possible.

        By default this function selects `ssh://` as the default schema
        for any url that has no explicit schema.

        Raises
        ------
        ValueError
            The provided url was invalid.

        Parameters
        ----------
        url
            The url to qualify.

        Returns
        -------
        str
            The qualified url.
        """
        _ = (self)
        return url if ':' in url else f"ssh://{url}"

    def extract_hostname(self, url: str) -> str:
        """
        Extracts the hostname from a given url. By default
        this is done via the the responsible connector.

        Raises
        ------
        ValueError
            The provided url was invalid.

        Parameters
        ----------
        url
            The url to extract the hostname from.

        Returns
        -------
        str
            The extracted hostname.
        """
        _ = (self)
        from fora.connectors.connector import Connector # pylint: disable=import-outside-toplevel
        if ':' not in url:
            raise ValueError("The given url doesn't include a schema")
        schema = url.split(':')[0]
        if schema not in Connector.registered_connectors:
            raise ValueError(f"Invalid url schema '{schema}'")
        return Connector.registered_connectors[schema].extract_hostname(url)

    def process_host_declarations(self) -> None:
        """
        Processes and modifies `hosts` to ensure each host is represented by a `HostDeclaration`
        object. Also checks that no duplicate host declarations are present.

        Raises
        ------
        ValueError
            Invalid hosts declaration (duplicate host or invalid definition)
        """
        # Unify declarations
        decls = {}
        for host in self.hosts:
            decl: HostDeclaration
            if isinstance(host, HostDeclaration):
                decl = host
            elif isinstance(host, str):
                decl = HostDeclaration(url=host)
            elif isinstance(host, dict):
                decl = HostDeclaration(**host)
            else:
                raise ValueError(f"invalid host declaration '{str(host)}'")

            # First qualify the url (by default this adds ssh:// to "naked" hostnames)
            decl.url = self.qualify_url(decl.url)
            # Next extract the indentifying "friendly" hostname which we need to find the module file for the host.
            decl.name = self.extract_hostname(decl.url)

            if decl.name in decls:
                raise ValueError(f"duplicate host '{str(decl.name)}' specified by '{host}'")
            decls[decl.name] = decl

        self.hosts = list(decls.values())

    def process_group_declarations(self) -> None:
        """
        Processes and modifies `groups` to ensure each host is represented by a `GroupDeclaration`
        object. Also checks that no duplicate group declarations are present and that the `all` group is defined.

        Raises
        ------
        ValueError
            Invalid groups declaration (duplicate group or invalid definition)
        """
        # No explicit definition was given. Therefore, automatically define groups
        # based on the groups that were assigned to hosts.
        if self.groups is None:
            self.groups = []
            for host in self.hosts:
                if isinstance(host, HostDeclaration):
                    self.groups.extend(host.groups)
                else:
                    raise RuntimeError("found invalid host declaration. Ensure that process_group_declarations is called after hosts were processed.")

            # Deduplicate
            self.groups = list(set(self.groups))

        # Unify declarations
        decls = {}
        for group in self.groups:
            decl: GroupDeclaration
            if isinstance(group, GroupDeclaration):
                decl = group
            elif isinstance(group, str):
                decl = GroupDeclaration(name=group)
            elif isinstance(group, dict):
                decl = GroupDeclaration(**group)
            else:
                raise ValueError(f"invalid group declaration '{str(group)}'")

            if decl.name in decls:
                raise ValueError(f"duplicate group '{str(decl.name)}' specified by '{group}'")
            decls[decl.name] = decl

        # Ensure "all" group is defined.
        if "all" not in decls:
            decls["all"] = GroupDeclaration(name="all")

        self.groups = list(decls.values())

    def ensure_used_groups_are_declared(self) -> None:
        """
        Ensure that all used groups are are actually declared.

        Raises
        ------
        ValueError
            An unknown group was used or an invalid declaration was encountered.
        """
        groups = set()
        assert self.groups is not None
        for group in self.groups:
            if isinstance(group, GroupDeclaration):
                groups.add(group.name)
            else:
                raise RuntimeError("found invalid group declaration. Ensure that ensure_used_groups_are_declared is called after hosts and groups were processed.")

        for host in self.hosts:
            if isinstance(host, HostDeclaration):
                for group in host.groups:
                    if group not in groups:
                        raise ValueError(f"Unknown group '{group}' used in declaration of host '{host.name}'")
            else:
                raise RuntimeError("found invalid host declaration. Ensure that ensure_used_groups_are_declared is called after hosts and groups were processed.")

    def process_inventory(self) -> None:
        """
        This function processes the declared hosts and groups and calculates
        dependent variables like `_topological_order`. This should be called after
        wrapping a module to ensure the wrapped module didn't supply any bogus declarations.

        Raises
        ------
        ValueError
            An invalid supplied value caused an error while processing.
        """
        self.process_host_declarations()
        self.process_group_declarations()
        self.ensure_used_groups_are_declared()

        self._topological_order = []
