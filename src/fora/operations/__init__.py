"""This package contains all standard operation modules."""

from fora.utils import import_submodules

# Import all submodules to ensure that decorators have a chance
# to register operations to a registry (e.g. package_managers).
import_submodules(__name__)
