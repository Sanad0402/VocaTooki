"""Moved to vocatooki/parrot_guard.py. This name stays an ALIAS of that module.

Aliased through sys.modules (not re-exported), so both names are the very same
module object: patching or reading either one affects the one real guard.
"""
import sys

from vocatooki import parrot_guard as _real

sys.modules[__name__] = _real
