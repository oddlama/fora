"""
Imports all standard connectors to register them by default.
"""

# Force inclusion of known connectors so they will be registered.
from .ssh import SshConnector

_ = (SshConnector)
