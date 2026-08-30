"""Guest-flow run type for the HTML runner.

The guest flow has no account, no class and no lesson range, so it cannot be a
`modes.MODES` entry — every mode there is a per-lesson callable driven by the
lesson loop. It is a RUN TYPE instead, sitting beside 'test_folder' and
'test_case'.

It needs no new execution path either. The 28 generated guest cases are exactly
the 7 languages x 4 English levels grid, each already linked to a pytest node,
so a tick-box selection resolves to a list of TC ids and the existing suite
runner takes it from there.

The wording of both lists is the wording the APP prints on its onboarding
screens, so what is ticked here reads the same as what a tester sees.
"""

import re

from runner import suite


# The guest cases live in one Rally folder.
GUEST_FOLDER = "TF296"

# App order, not alphabetical: this is how the onboarding screens list them.
LANGUAGES = ["Arabic", "French", "German", "Hebrew", "Portuguese", "Spanish",
             "Turkish"]
LEVELS = ["Beginning Literacy", "Elementary Proficiency",
          "Intermediate Proficiency", "Advanced Proficiency"]

# The native language is what a guest is chosen BY, so it leads the UI and is
# the group that comes pre-ticked; a level still has to be picked as well.
DEFAULT_LANGUAGES = ["Arabic"]
DEFAULT_LEVELS = ["Beginning Literacy"]


def _field(description, label):
    """Read 'Label: value' out of a case description."""
    match = re.search(rf"^{label}:\s*(.+)$", description or "", re.MULTILINE)
    return match.group(1).strip() if match else ""


def grid():
    """Every guest case, tagged with the language and level it registers.

    Read from the suite rather than from the test files: the suite is what the
    runner executes, so a case that is missing or unlinked here shows up as
    exactly that instead of looking runnable.
    """
    out = []
    for case in suite.load()["test_cases"]:
        if case.get("folder") != GUEST_FOLDER:
            continue
        description = case.get("description", "")
        out.append({
            "tc_id": case.get("id", ""),
            "name": case.get("name", ""),
            "language": _field(description, "Language"),
            "level": _field(description, "Difficulty"),
            "gender": _field(description, "Avatar Gender"),
            "linked": bool((case.get("action") or {}).get("nodeid")),
        })
    return out


def options():
    """What the UI needs to draw the two checkbox groups."""
    cases = grid()
    return {
        "languages": LANGUAGES,
        "levels": LEVELS,
        "default_languages": DEFAULT_LANGUAGES,
        "default_levels": DEFAULT_LEVELS,
        "cases": cases,
        # Surfaced so the panel can say WHY a batch is refused before the user
        # ticks half the grid and presses Run.
        "one_at_a_time": True,
        "reset_note": ("Every guest registration needs the app's data cleared "
                       "and the app restarted first, so guest cases run one at "
                       "a time."),
    }


def resolve(languages, levels):
    """(case ids, warnings) for the ticked language/level pairs.

    Pairs are walked language-major, in the app's own order, so the plan reads
    the way the grid does rather than in whatever order the boxes were clicked.
    """
    picked_languages = [l for l in LANGUAGES if l in set(languages or [])]
    picked_levels = [l for l in LEVELS if l in set(levels or [])]

    warnings = []
    unknown = sorted(set(languages or []) - set(LANGUAGES))
    if unknown:
        warnings.append(f"Unknown language(s) ignored: {', '.join(unknown)}")
    unknown = sorted(set(levels or []) - set(LEVELS))
    if unknown:
        warnings.append(f"Unknown English level(s) ignored: {', '.join(unknown)}")

    by_pair = {(c["language"], c["level"]): c for c in grid()}
    ids = []
    for language in picked_languages:
        for level in picked_levels:
            case = by_pair.get((language, level))
            if case is None:
                warnings.append(f"No guest case for {language} / {level}.")
                continue
            if not case["linked"]:
                warnings.append(
                    f"{case['tc_id']} ({language} / {level}) has no pytest test "
                    f"linked — generate it first.")
                continue
            ids.append(case["tc_id"])
    return ids, warnings


def validate(cfg):
    """Errors that stop a guest run before it starts."""
    languages = cfg.get("guest_languages") or []
    levels = cfg.get("guest_levels") or []
    errors = []
    if not languages:
        errors.append("Pick at least one native language.")
    if not levels:
        errors.append("Pick at least one English level.")
    return errors
