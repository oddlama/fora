"""Provides example deploys, which can be used as a starting point."""

import os
from pathlib import Path
import sys
from textwrap import dedent
from typing import Literal, NoReturn

from fora import logger
from fora.utils import print_status

_inventory_def = dedent("""\
# Define which hosts belong to this inventory.
hosts = [
    "local:",                   # Local machine, executed as the user who invokes fora
    # "example",                # Some remote machine via ssh (probably requires matching entry in `.ssh/config`)
    # "ssh://root@example.com", # An explicit user on a remote machine via ssh
]
""")

_localhost_def = dedent("""\
# Define a (different) url for this host. Useful
# if the inventory entry is just a name like "localhost"
# url = "ssh://root@localhost"

# Define variables for this host
somevariable = "this was defined by the host"
""")

_nginx_add_site = dedent("""\
from fora.operations import files

@Params
class params:
    site: str

files.template(
    name="Create the site definition",
    src="templates/site.j2",
    dest=f"/etc/nginx/sites/{params.site}")
files.line_in_file(
    name="Add ",
    file="/etc/nginx/sites",
    line=f"sites/{params.site}")
""")

_nginx_site_j2 = dedent("""\
{{ fora_managed }}
server {
    # ...
}
""")

_nginx_install = dedent("""\
from fora.operations import system

system.package(
    name="Install the application",
    packages=["nginx"])
system.service(
    name="(Re-)start the service",
    service="nginx",
    state="restarted",
    enabled=True)
""")

_modular_nginx_deploy = dedent("""\
from fora.operations import local, system

local.script(
    script="tasks/example_task/install.py")
local.script(
    name="Add test1.example.com site",
    script="tasks/example_task/add_site.py",
    params=dict(site="site1"))
local.script(
    name="Add test2.example.com site",
    script="tasks/example_task/add_site.py",
    params=dict(site="site2"))

system.service(
    name="(Re-)start the service",
    service="nginx",
    state="restarted")
""")

_all_def = dedent("""\
somevariable = "defined fallback in 'all' group"
""")

def _create_dirs(dirs: list[str]) -> None:
    """
    Creates the given list of directories in the current working directory.

    Parameters
    ----------
    dirs
        The directories to create
    """
    for d in dirs:
        Path(d).mkdir(exist_ok=True)

def _write_file(file: str, content: str) -> None:
    """
    Writes the given content to the specified file.

    Parameters
    ----------
    file
        The file
    content
        The content
    """
    with open(file, "w", encoding="utf-8") as f:
        f.write(content)

def init_structure_minimal() -> None:
    """Creates a minimal deploy structure."""
    _create_dirs(["hosts"])
    _write_file("hosts/localhost.py", _localhost_def)
    _write_file("inventory.py", _inventory_def)
    _write_file("deploy.py", dedent("""\
        from fora import host
        from fora.operations import files

        files.content(
            name="A temporary example file",
            content=f"Hello from {host.name}, also remember that {host.somevariable=}!",
            dest="/tmp/hello_world")
        """))

def init_structure_flat() -> None:
    """Creates a flat deploy structure."""
    _create_dirs(["hosts", "groups", "tasks", "files", "templates"])
    _write_file("hosts/localhost.py", _localhost_def)
    _write_file("groups/all.py", _all_def)
    _write_file("inventory.py", _inventory_def)
    _write_file("tasks/example_task.py", dedent("""\
        from fora.operations import files

        files.upload(
            name="A temporary example file",
            src="../files/staticfile",
            dest="/tmp/hello_world")
        """))
    _write_file("tasks/example_params.py", dedent("""\
        from fora.operations import files

        @Params
        class params:
            filename: str

        script_var = "this is a fallback value defined in a script"

        files.template(
            name="Render a template to the file that was specified in the parameters",
            src="../templates/template.j2",
            dest=params.filename)
        """))
    _write_file("deploy.py", dedent("""\
        from fora.operations import local

        local.script(
            name="Run example task",
            script="tasks/example_task.py")
        local.script(
            name="Run parameter example task",
            script="tasks/example_params.py",
            params=dict(filename="/tmp/paramtest.txt"))
        """))
    _write_file("templates/template.j2", dedent("""\
        {{ fora_managed }}
        This file was specified by script parameters! See the fallback to the script var for the host: {{host.script_var}}
        """))
    _write_file("files/staticfile", dedent("""\
        Hello I am static content!
        """))

def init_structure_dotfiles() -> None:
    """Creates a dotfiles deploy structure."""
    _write_file("deploy.py", dedent("""\
        from fora import host
        from fora.operations import files

        # Get home directory of current user
        home = host.home_dir()

        # zsh
        files.upload(src="zsh/zshrc", dest=f"{home}/.zshrc")

        # kitty
        files.directory(path=f"{home}/.config/kitty")
        files.upload(src="kitty/kitty.conf", dest=f"{home}/.config/kitty/kitty.conf")

        # neovim
        files.directory(path=f"{home}/.config/nvim")
        files.upload(src="neovim/init.lua", dest=f"{home}/.config/init.lua")
        """))

def init_structure_modular() -> None:
    """Creates a modular deploy structure."""
    _create_dirs(["hosts", "groups", "tasks", "tasks/example_task", "tasks/example_task/files", "tasks/example_task/templates"])
    _write_file("hosts/localhost.py", _localhost_def)
    _write_file("groups/all.py", _all_def)
    _write_file("inventory.py", _inventory_def)
    _write_file("tasks/example_task/install.py", _nginx_install)
    _write_file("tasks/example_task/add_site.py", _nginx_add_site)
    _write_file("tasks/example_task/templates/site.j2", _nginx_site_j2)
    _write_file("deploy.py", _modular_nginx_deploy)

def init_structure_staging_prod() -> None:
    """Creates a staging_prod deploy structure."""
    _create_dirs(["inventories", "inventories/hosts", "inventories/groups", "tasks", "tasks/example_task", "tasks/example_task/files", "tasks/example_task/templates"])
    _write_file("inventories/hosts/example.py", dedent("""\
            # Same hostfile definition for all example.com hosts, to avoid repetition
            domain = "example.com"
        """))
    _write_file("inventories/groups/all.py", _all_def)
    _write_file("inventories/staging.py", dedent("""\
            import os

            # These are implicit variables that will be defined on the `all` group.
            # Useful to define global variables from the inventory
            def global_variables():
                return dict(api_key=os.getenv("API_KEY_STAGING"))

            hosts = [dict(url="staging1.example.com", file="hosts/example.py", groups=["staging"]),
                     dict(url="staging2.example.com", file="hosts/example.py", groups=["staging"])]
        """))
    _write_file("inventories/prod.py", dedent("""\
            import os

            # These are implicit variables that will be defined on the `all` group.
            # Useful to define global variables from the inventory
            def global_variables():
                return dict(api_key=os.getenv("API_KEY_PROD"))

            hosts = [dict(url="prod1.example.com", file="hosts/example.py", groups=["prod"]),
                     dict(url="prod2.example.com", file="hosts/example.py", groups=["prod"]),
                     dict(url="prod3.example.com", file="hosts/example.py", groups=["prod"]),
                     dict(url="prod4.example.com", file="hosts/example.py", groups=["prod"])]
        """))
    _write_file("tasks/example_task/install.py", _nginx_install)
    _write_file("tasks/example_task/add_site.py", _nginx_add_site)
    _write_file("tasks/example_task/templates/site.j2", _nginx_site_j2)
    _write_file("deploy.py", _modular_nginx_deploy)

def init_deploy_structure(layout: Literal["minimal", "flat", "dotfiles", "modular", "staging_prod"]) -> NoReturn: # type: ignore[misc]
    """
    Initializes the current directory with a default deploy structure, if it is empty.
    Prompts the user to confirm operation if the current directory is not empty.

    Parameters
    ----------
    layout
        The layout for the deploy.

    Raises
    ------
    ValueError
        Invalid layout.
    """
    if layout not in _init_fns:
        raise ValueError(f"Unknown deploy layout structure '{layout}'")

    # Check if directory is empty. If not, ask whether to proceed.
    cwd = os.getcwd()
    if any(os.scandir(cwd)):
        response = input(f"{logger.col('[1;33m')}warning:{logger.col('[m')} current directory is not empty, proceed anyway? (conflicting files will be overwritten) [y/N] ")
        if response.lower() not in ["y", "yes"]:
            sys.exit(1)

    print_status("init:", f"creating {logger.col('[1;33m')}{layout}{logger.col('[m')} deploy structure")
    _init_fns[layout]()
    sys.exit(0)

_init_fns = {
    "minimal":      init_structure_minimal,
    "flat":         init_structure_flat,
    "dotfiles":     init_structure_dotfiles,
    "modular":      init_structure_modular,
    "staging_prod": init_structure_staging_prod,
}
