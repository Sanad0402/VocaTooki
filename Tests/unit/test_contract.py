"""The framework's CONTRACT: nothing a test, the runner or a solver relies on may disappear.

`contract_snapshot.json` froze, on 2026-09-22, every top-level name that
`Utilities.utilsdemo` and `Activities.activitiesDemo` offered, and which solver
each activity scene dispatches to. The 49 generated Rally tests, the runner,
the page objects and the solvers all reach the framework through those two
module names, so a reorganisation is only safe while every one of them still
resolves there — and every scene still reaches the same solver.

New names are fine. A name that has to go on purpose is removed from the
snapshot in the same commit, where the review can see it.

Run offline (no app needed):  python -m pytest Tests/unit --noconftest -q
"""

import json
import logging
import pathlib

import pytest

logging.disable(logging.WARNING)

from Activities import activitiesDemo  # noqa: E402
from Utilities import utilsdemo  # noqa: E402

SNAPSHOT = json.loads((pathlib.Path(__file__).parent / "contract_snapshot.json")
                      .read_text(encoding="utf-8"))
MODULES = {"utilsdemo": utilsdemo, "activitiesDemo": activitiesDemo}


@pytest.mark.parametrize("module_name", sorted(MODULES))
def test_every_frozen_name_still_resolves(module_name):
    module = MODULES[module_name]
    missing = [n for n in SNAPSHOT[module_name] if not hasattr(module, n)]
    assert not missing, f"{module_name} lost {len(missing)} name(s): {missing[:20]}"


@pytest.mark.parametrize("module_name", sorted(MODULES))
def test_frozen_callables_are_still_callable(module_name):
    module = MODULES[module_name]
    broken = [n for n, kind in SNAPSHOT[module_name].items()
              if kind in ("function", "type") and hasattr(module, n)
              and not callable(getattr(module, n))]
    assert not broken, f"{module_name}: no longer callable: {broken}"


def test_every_scene_reaches_the_same_solver():
    current = {k: f"{v.__module__.split('.')[-1]}.{v.__name__}"
               for k, v in utilsdemo.get_activity_solver_map().items()}
    frozen = SNAPSHOT["solver_map"]
    lost = sorted(set(frozen) - set(current))
    changed = {k: (frozen[k], current[k]) for k in frozen if k in current
               and frozen[k].split(".")[-1] != current[k].split(".")[-1]}
    assert not lost, f"scenes no longer dispatched: {lost}"
    assert not changed, f"scenes now dispatch to a different solver: {changed}"


def test_generator_templates_only_use_existing_names():
    """Generated tests call utilsdemo.<name> from text templates — those must exist too."""
    import re
    source = (pathlib.Path(__file__).parents[2] / "runner" / "test_generator.py").read_text(
        encoding="utf-8")
    used = set(re.findall(r"utilsdemo\.([A-Za-z_][A-Za-z0-9_]*)", source))
    missing = sorted(n for n in used if not hasattr(utilsdemo, n))
    assert not missing, f"the generator writes calls to names that do not exist: {missing}"
