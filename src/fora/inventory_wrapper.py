"""Provides the inventory wrapper for all inventory related functionality."""
from __future__ import annotations

import os
from copy import copy
from dataclasses import dataclass, field
from glob import glob
from types import ModuleType, SimpleNamespace
from typing import Any, Literal, Optional, Union, cast

from fora.types import GroupWrapper, HostWrapper, ModuleWrapper, VariableActionSnapshot
from fora.utils import CycleError, load_py_module, print_error, rank_sort, transitive_dependencies

def is_bequestable(attr: str, value: Any) -> bool:
    """Returns true if this variable will be inherited by modules with higher ordering precedence."""
    return not (attr.startswith("_") or attr in GroupWrapper.__annotations__ or attr in GroupWrapper.__dict__ or isinstance(value, ModuleType))

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

    _is_initialized: bool = False
    """A flag to indicate whether or not the inventory is fully initialized."""

    _host_decls: dict[str, HostDeclaration] = field(default_factory=dict)
    """The validated dictionary of host declarations. Set when the inventory is processed."""

    _group_decls: dict[str, GroupDeclaration] = field(default_factory=dict)
    """The validated dictionary of group declarations. Set when the inventory is processed."""

    _group_ranks_min: dict[str, int] = field(default_factory=dict)
    """The top-down rank for each group. Set when the inventory is processed."""

    _group_ranks_max: dict[str, int] = field(default_factory=dict)
    """The bottom-up rank for each group. Set when the inventory is processed."""

    _topological_order: list[str] = field(default_factory=list)
    """A topological order of all groups in this inventory. Set when the inventory is processed."""

    loaded_hosts: dict[str, HostWrapper] = field(default_factory=dict)
    """All loaded hosts. Set when the inventory is processed."""

    def is_initialized(self) -> bool:
        """Returns True if the inventory is fully initialized."""
        return self._is_initialized

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
        _ = (self)
        return {}

    def available_groups(self) -> set[str]:
        """
        Returns the set of available groups in this inventory.
        By default each module file in `groups_dir` (relative to the inventory module)
        creates a group of the same name, disregarding the `.py` extension.

        Note that the `all` group will always be made available, even if it isn't explicitly
        returned by this function. This function should only return groups that have a
        corresponding module file.

        Raises
        ------
        RuntimeError
            The inventory has no associated module file.

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
            The inventory has no associated module file.

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

    def preprocess_host_declarations(self) -> None:
        """
        Processes and modifies `hosts` to ensure each host is represented by a `HostDeclaration`
        object. Also checks that no duplicate host declarations are present.

        Raises
        ------
        ValueError
            Invalid hosts declaration (duplicate host or invalid definition)
        """
        # Unify declarations
        for host in self.hosts:
            decl: HostDeclaration
            if isinstance(host, HostDeclaration):
                decl = host
            elif isinstance(host, str):
                decl = HostDeclaration(url=host)
            elif isinstance(host, dict):
                decl = HostDeclaration(**host)
            else:
                raise ValueError(f"Invalid host declaration '{str(host)}'")

            # First qualify the url (by default this adds ssh:// to "naked" hostnames)
            decl.url = self.qualify_url(decl.url)
            # Next extract the indentifying "friendly" hostname which we need to find the module file for the host.
            decl.name = self.extract_hostname(decl.url)

            if decl.name in self._host_decls:
                raise ValueError(f"Duplicate host '{str(decl.name)}' specified by '{host}'")

            self._host_decls[decl.name] = decl

    def preprocess_group_declarations(self) -> None:
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
            for host in self._host_decls.values():
                self.groups.extend(host.groups)

            # Deduplicate
            self.groups = list(set(self.groups))

        # Unify declarations
        for group in self.groups:
            decl: GroupDeclaration
            if isinstance(group, GroupDeclaration):
                decl = group
            elif isinstance(group, str):
                decl = GroupDeclaration(name=group)
            elif isinstance(group, dict):
                decl = GroupDeclaration(**group)
            else:
                raise ValueError(f"Invalid group declaration '{str(group)}'")

            if decl.name in self._group_decls:
                raise ValueError(f"Duplicate group '{str(decl.name)}' specified by '{group}'")

            # Deduplicate before and after
            decl.before = list(set(decl.before))
            decl.after = list(set(decl.after) | set(["all"]))

            self._group_decls[decl.name] = decl

        # Ensure "all" group is defined.
        if "all" not in self._group_decls:
            self._group_decls["all"] = GroupDeclaration(name="all")

    def ensure_used_groups_are_declared(self) -> None:
        """
        Ensure that all used groups are are actually declared.

        Raises
        ------
        ValueError
            An unknown group was used or an invalid declaration was encountered.
        """
        for host in self._host_decls.values():
            for group_name in host.groups:
                if group_name not in self._group_decls:
                    raise ValueError(f"Unknown group '{group_name}' used in declaration of host '{host.name}'")

        for group in self._group_decls.values():
            for after in group.after:
                if after not in self._group_decls:
                    raise ValueError(f"Unknown group '{after}' used in after set of group '{group.name}'")
            for before in group.before:
                if before not in self._group_decls:
                    raise ValueError(f"Unknown group '{before}' used in after set of group '{group.name}'")

    def merge_group_dependencies(self) -> None:
        """
        Merges the dependencies of all group declarations.
        This will ensure that if `"a" in b.before` then `"b" in a.after` and vice versa.
        """
        # Unify `before` and `after` dependencies
        for group in self._group_decls.values():
            for before in group.before:
                self._group_decls[before].after.append(group.name)

        # Deduplicate `after`, clear `before`
        for group in self._group_decls.values():
            group.before = []
            group.after = list(set(group.after))

        # Recalculate `before` from `after`
        for group in self._group_decls.values():
            for after in group.after:
                self._group_decls[after].before.append(group.name)

        # Deduplicate `before`
        for group in self._group_decls.values():
            group.before = list(set(group.before))

    def detect_self_dependencies(self) -> None:
        """
        Raises a `ValueError` when a group depends on itself.

        Raises
        ------
        ValueError
            A self-dependency was detected.
        """
        for group in self._group_decls.values():
            if group.name in group.before or group.name in group.after:
                raise ValueError(f"Group '{group.name}' must not depend on itself")

    def calculate_topological_order(self) -> None:
        """
        Topologically sorts the group declarations using their stated (and preprocessed) dependencies.
        Also validates that the dependencies are not cyclic.

        Raises
        ------
        ValueError
            Either a cycle was detected or The loaded inventory was invalid.
        """
        # Rank sort from bottom-up and top-down to calculate minimum rank and maximum rank.
        # This is basically the earliest time a group might be applied (exactly after all dependencies
        # were processed), and the latest time (any other group requires this one to be processed first).
        #
        # Rank numbers are already 0-based. This means in the top-down view, the root node
        # has top-rank 0 and a high bottom-rank, and all leaves have bottom_rank 0 and a high top-rank.
        l_before = lambda g: self._group_decls[g].before
        l_after = lambda g: self._group_decls[g].after

        group_names = list(self._group_decls)

        try:
            ranks_t = rank_sort(group_names, l_after, l_before) # Top-down
            ranks_b = rank_sort(group_names, l_before, l_after) # Bottom-up
        except CycleError as e:
            raise ValueError(f"Dependency cycle detected! The cycle includes {e.cycle}.") from None

        # Find the maximum rank. Both ranking systems have the same number of ranks. This is
        # true because the longest dependency chain determines the amount of ranks, and all dependencies
        # are the same.
        ranks_t_max = max(ranks_t.values())
        ranks_b_max = max(ranks_b.values())
        assert ranks_t_max == ranks_b_max
        n_ranks = ranks_b_max

        # Rebase bottom-ranks on top-ranks. We now want to transform top-ranks into minimum-ranks and
        # bottom-ranks into maximum-ranks, as viewed from a top-down scheme. I.e. we want to know the
        # range of ranks a module could occupy in any valid topological order. Therefore, we will simply
        # subtract all bottom-ranks from the highest rank number to get maximum-ranks. The top-down ranks
        # are already the minimum ranks.
        self._group_ranks_min = ranks_t
        self._group_ranks_max = {k: n_ranks - v for k,v in ranks_b.items()}

        # Save the topological order based on the top-rank
        group_names.sort(key=lambda g: self._group_ranks_min[g])
        self._topological_order = group_names

    def load(self) -> None:
        """
        This function preprocesses the declared hosts and groups, calculates
        dependent variables like `_topological_order` and actually instanciates
        required modules. This should be called after wrapping a module to ensure
        the wrapped module didn't supply any bogus declarations and that all
        dynamic definitions are fully loaded.

        Raises
        ------
        ValueError
            An invalid supplied value caused an error while processing.
        """
        # Process user defined declarations
        self.preprocess_host_declarations()
        self.preprocess_group_declarations()

        # Ensure validity of used groups
        self.ensure_used_groups_are_declared()

        # Unify `before` and `after` dependencies
        self.merge_group_dependencies()
        self.detect_self_dependencies()

        self.calculate_topological_order()

        # Instanciate hosts
        self.loaded_hosts = {host: self.instanciate_host(host) for host in self._host_decls}
        self._is_initialized = True

    def load_group(self, name: str, initializer: Optional[GroupWrapper]) -> GroupWrapper:
        """
        Creates a new instance of the given group.

        Parameters
        ----------
        name
            The group to instanciate.
        initializer
            A previously loaded group module that should be used to initialize
            this module's global variables before its code is executed.

        Returns
        -------
        GroupWrapper
            A new instance of the declared group.
        """
        declaration = self._group_decls[name]
        if name not in self._group_decls:
            raise ValueError("Invalid instanciation request of unknown group. Ensure that the group has been defined in the inventory.")

        wrapper = GroupWrapper(declaration.name)
        module_file = self.group_module_file(declaration.name) if declaration.file is None else declaration.file

        # pylint: disable=import-outside-toplevel
        import fora
        def pre_exec(module: Any) -> None:
            fora.group = wrapper
            wrapper.wrap(module, copy_members=True, copy_functions=True)

            if wrapper.name == "all":
                # Add predefined global variables before the "all" group module is instanciated
                setattr(wrapper, "fora_managed", "This file is managed by fora.")
                for attr, val in self.global_variables().items():
                    setattr(wrapper, attr, val)

            # Initialize global namespace if an initializer was provided.
            if initializer is not None:
                for attr, value in vars(initializer).items():
                    if is_bequestable(attr, value):
                        setattr(module, attr, value)

        # Instanciate module file if it exists, else return default definition
        if module_file is None or not os.path.exists(module_file):
            # Check if the module file is required because it was explicitly set
            if declaration.file is not None:
                raise ValueError(f"Module file for {declaration} does not exist but was explicitly specified")
            pre_exec(SimpleNamespace())
        else:
            load_py_module(module_file, pre_exec=pre_exec)

        fora.group = cast(GroupWrapper, None)
        return wrapper

    def load_host(self, name: str, initializer: Optional[GroupWrapper]) -> HostWrapper:
        """
        Creates a new instance of the given host.

        Parameters
        ----------
        name
            The host to instanciate.
        initializer
            A previously loaded host module that should be used to initialize
            this module's global variables before its code is executed.

        Returns
        -------
        HostWrapper
            A new instance of the declared host.
        """
        declaration = self._host_decls[name]
        if name not in self._host_decls:
            raise ValueError("Invalid instanciation request of unknown host. Ensure that the host has been defined in the inventory.")

        assert declaration.name is not None
        wrapper = HostWrapper(declaration.name, declaration.url, groups=declaration.groups)
        module_file = self.host_module_file(declaration.name) if declaration.file is None else declaration.file

        # pylint: disable=import-outside-toplevel
        import fora
        def pre_exec(module: Any) -> None:
            fora.host = wrapper
            wrapper.wrap(module, copy_members=True, copy_functions=True)

            # Initialize global namespace if an initializer was provided.
            if initializer is not None:
                for attr, value in vars(initializer).items():
                    if is_bequestable(attr, value):
                        setattr(module, attr, value)

        # Instanciate module file if it exists, else return default definition
        if module_file is None or not os.path.exists(module_file):
            # Check if the module file is required because it was explicitly set
            if declaration.file is not None:
                raise ValueError(f"Module file for {declaration} does not exist but was explicitly specified")
            pre_exec(SimpleNamespace())
        else:
            load_py_module(module_file, pre_exec=pre_exec)

        fora.host = cast(HostWrapper, None)
        return wrapper

    # We need a way to allow groups and host modules to override variables from other
    # low precedence groups, or to extend a dictionary, list or some other object defined
    # previously. How do we accomplish this?
    #
    # One approach that I tried was to implement a fully hierarchical lookup for the
    # host module that did go through all groups in reverse order of precedence and return the
    # as soon as a variable was defined on one of the modules. Apart from the complexity,
    # a problem with this approach was that modifying existing variables like dictionaries from
    # parent modules wasn't easy or clean. We would've had to distinguish between those cases
    # depending on a type annotation of the variable. While this was possible, it introduced
    # an unnecessary conecept of annotating some variables to gain special "magic" behavior
    # and a lot of complexity. At that time, the depndencies between modules was defined in
    # the modules themselves, which made it impossible to inherit variables between groups.
    #
    # The approach I settled on now is to define groups and group dependencies in the inventory,
    # allowing us to load group modules in the correct order for each host. By doing this, we can
    # bequest (copy) all variables that have been defined until that point to the next module that
    # will be loaded, be it a host or another group. This allows any module to access and modify
    # all inherited variables easily, as they are just part of the global variables.
    def instanciate_host(self, host: str) -> HostWrapper:
        """
        This function instanciates the given host by recursively loading all groups
        in the correct topological order and propagating variables until finally the
        host module is instanciated.

        Different hosts don't share group instanciations, as the groups may modify
        variables from previously loaded groups (e.g. add to dictionaries). As two
        different hosts can share just a single group out of many, and because groups
        need to modify global state in-place, we cannot reuse a group instanciated for
        another host.

        This loader asserts that a group doesn't redefine (as in completely overwrite)
        an existing variable, when this group doesn't have a dependency on the group
        from where the instanciation is overwritten. This prevents ambiguous definitions
        caused by the two groups having arbitrary relative ordering. Although this does
        assume that a group only modifies existing variables by adding information
        (e.g. appending to list or adding keys to a dict) instead of removing information.

        Parameters
        ----------
        host
            The name of the host to instanciate.

        Retruns
        -------
        HostWrapper
            The instanciated host.
        """
        # We begin by figuring out all relevant groups for this host. This simply
        # are all transitive dependencies (`group.after`) of all direct groups of this host.
        assert host in self._host_decls
        transitive_groups = transitive_dependencies(set(self._host_decls[host].groups), lambda g: set(self._group_decls[g].after))
        groups_in_order = filter(transitive_groups.__contains__, self._topological_order)

        # Next, we iterate through all groups in topological order, and load the
        # respective group with its globals initialized to the result from loading
        # the previous group. The initial group (probably the "all" group) gets no
        # special pre-defined globals.
        initializer: Optional[GroupWrapper] = None

        # Additionally, we will track for each variable where it was initially defined,
        # and each point where it was changed. This allows us to detect when a group module
        # overwrites a variable witout having an (transitive) dependency to the module
        # which defined this variable before. This would result in an arbitrary ordering
        # of those two modules in the topological order, so the resulting variable would be
        # ambiguous. As a side effect we can later store this history on the host wrapper,
        # as it is useful for the inspector output of `fora --inspect-inventory`.
        variable_action_history: dict[str, list[VariableActionSnapshot]] = {}

        # We record all encountered variable conflicts while loading. If we find any,
        # we need to raise an error later, to allow all conflicts to be shown to the user first.
        conflicts: list[tuple[Literal["definition", "modification"], ModuleWrapper, Literal["definition", "modification"], ModuleWrapper, str]] = []

        def record_variable_change(actor: ModuleWrapper, initializer: Optional[ModuleWrapper], attr: str, value: Any, record_conflicts_group: Optional[GroupWrapper] = None) -> None:
            if not is_bequestable(attr, value):
                return

            # If the variable changed identity compared to the value it was initialized with,
            # it was overwritten (or it was newly defined). We want to record this in our
            # definition history. We also compare against a snapshot of the value to detect
            # modification instead of redefinition.
            previous_value = None if attr not in variable_action_history else variable_action_history[attr][-1].value
            was_modified = previous_value != value
            was_overwritten = hasattr(initializer, attr) and getattr(initializer, attr) is not value
            cur_action: Literal["definition", "modification"] = "modification" if was_modified and not was_overwritten else "definition"

            if initializer is None or was_overwritten or was_modified:
                # If the variable was actually overwritten, we need to make sure that this module
                # was allowed to overwrite it. Otherwise, we record that this is a variable
                # conflict and raise an exception later, once we found all offending variables.
                if record_conflicts_group is not None and initializer is not None and attr in variable_action_history:
                    # Determine if the ranks of this group and any previous defining module overlap
                    # (which means they would share a common possible rank). If that is the case,
                    # they don't have any dependency on each other and overwriting is forbidden
                    # as their relative order is arbitrary. We already know that the current group
                    # is ordered after the previous group, as we are iterating in topological order,
                    # so a problem would only arise if the previous group's maximum possible rank
                    # overlaps with our minimum required rank.
                    for prev in variable_action_history[attr]:
                        if self._group_ranks_max[prev.actor.name] >= self._group_ranks_min[record_conflicts_group.name]:
                            conflicts.append((prev.action, prev.actor, cur_action, actor, attr))

                # Record this change for later analyses
                variable_action_history.setdefault(attr, []).append(VariableActionSnapshot(cur_action, actor, copy(value)))

        for group in groups_in_order:
            group_wrapper = self.load_group(group, initializer)
            for attr, value in vars(group_wrapper).items():
                record_variable_change(group_wrapper, initializer, attr, value, record_conflicts_group=group_wrapper)

            # Use the newly loaded group as the initializer for the next group
            initializer = group_wrapper

        if len(conflicts) > 0:
            for prev_action, prev_def, new_action, new_def, attr in conflicts:
                print_error(f"{new_action.capitalize()} of '{attr}' is in conflict with {prev_action} at {prev_def.definition_file()}", loc=new_def.definition_file())
            raise ValueError("Conflict in variable assignment from two groups with ambiguous ordering. Insert dependency or remove one definition.")

        # Finally instanciate the actual host.
        host_wrapper = self.load_host(host, initializer)
        # Update the variable action history one more time to include
        # definitions from the host module.
        for attr, value in vars(host_wrapper).items():
            record_variable_change(host_wrapper, initializer, attr, value)

        # Transfer the variable action history to the host wrapper,
        # pylint: disable=protected-access
        host_wrapper._variable_action_history = variable_action_history
        return host_wrapper
