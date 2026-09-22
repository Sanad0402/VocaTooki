"""Renamed to Pages/start_screen.py. This old name stays an ALIAS of that module.

Aliased through sys.modules, so both names are the very same module object -
code (and generated tests) that import the old name keep working unchanged.
"""
import sys

from Pages import start_screen as _real

sys.modules[__name__] = _real
