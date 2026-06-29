"""
Console bootstrap: import the whole project into the Python console.

Usage in the PyCharm Python Console (or any REPL started at the project root):

from console_imports import *

altdriver = AltDriver(

    host="127.0.0.1",
    port=13000,
    enable_logging=False
)
altdriver = AltDriver
from alttester import By, AltKeyCode, AltDriver

from Activities.activitiesDemo import *

This puts the project root on sys.path, imports every project module, and
pulls all of their public names (functions, classes, constants) into the
current namespace. Each module is loaded independently, so a module that
fails to import (e.g. a missing dependency) is reported and skipped rather
than aborting the whole load.
"""

import importlib
import os
import sys

# --- Make sure the project root is importable ----------------------------
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Modules to load, in dependency-friendly order.
_MODULES = [
    "data.test_users",
    "Utilities.wait_utils",
    "Utilities.utils_audio",
    "Utilities.utilsdemo",
    "Activities.activitiesDemo",
    "Pages.base_page",
    "Pages.LoginPage",
    "Pages.StartScreen",
    "Pages.map_page",
    "Pages.new_page",
]

# Short aliases so you can also reach modules namespaced, e.g. `act.search(...)`.
_ALIASES = {
    "Utilities.utilsdemo": "utils",
    "Utilities.utils_audio": "audio",
    "Utilities.wait_utils": "waits",
    "Activities.activitiesDemo": "act",
    "data.test_users": "users",
}

loaded = []
failed = {}


def _public_names(module):
    """Names a module exports: respect __all__, else all non-underscore names."""
    if hasattr(module, "__all__"):
        return list(module.__all__)
    return [n for n in vars(module) if not n.startswith("_")]


def _load_all(target_namespace):
    for name in _MODULES:
        try:
            module = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - report and continue
            failed[name] = f"{type(exc).__name__}: {exc}"
            continue

        loaded.append(name)

        # Bind a short alias to the module object, if configured.
        alias = _ALIASES.get(name)
        if alias:
            target_namespace[alias] = module

        # Pull the module's public names into the namespace.
        for public in _public_names(module):
            target_namespace[public] = getattr(module, public)

    # Report.
    print(f"[console_imports] loaded {len(loaded)} module(s): {', '.join(loaded)}")
    if _ALIASES:
        present = {a: m for m, a in _ALIASES.items() if m in loaded}
        if present:
            print("[console_imports] aliases: "
                  + ", ".join(f"{a} -> {m}" for a, m in present.items()))
    if failed:
        print("[console_imports] FAILED to import:")
        for name, err in failed.items():
            print(f"    - {name}: {err}")


# Load into this module's globals so `from console_imports import *` re-exports them.
_load_all(globals())


def reload_all():
    """Re-import every module (useful after editing code mid-session)."""
    for name in list(loaded):
        try:
            importlib.reload(importlib.import_module(name))
        except Exception as exc:  # noqa: BLE001
            print(f"[console_imports] reload failed for {name}: {exc}")
    _load_all(globals())
