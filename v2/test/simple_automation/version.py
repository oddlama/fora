"""
Provides version information
"""

import re

__version__ = '0.9.6'

def _parse_version_info():
    matches = re.match(r'(\d+).(\d+).(\d+)', __version__)
    if matches is None:
        return tuple()
    return tuple(int(p) for p in matches.groups())
version_info = _parse_version_info()

__all__ = ('__version__', 'version_info')
