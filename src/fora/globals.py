"""Stores all global state."""

import argparse
from typing import cast
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from fora.remote_settings import RemoteSettings

args: argparse.Namespace = cast(argparse.Namespace, None)
"""
The global logger. Should be used for all user-facing information logging to ensure
that this information is displayed in a proper format and according to the user's
verbosity preferences.
"""

jinja2_env: Environment = Environment(
    loader=FileSystemLoader('.', followlinks=True),
    autoescape=False,
    undefined=StrictUndefined)
"""The jinja2 environment used for templating."""

# The as_user, as_group, owner, group attributes will be filled in automatically
# by the connection, once we know as which user we are operating.
base_remote_settings = RemoteSettings(
    as_user="root",
    as_group="root",
    owner="root",
    group="root",
    file_mode="600",
    dir_mode="700",
    umask="077",
    cwd="/tmp")
"""The base remote settings that will be used if no other preferences are given."""
