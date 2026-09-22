"""The Unity scene names the framework recognises - plain constants, imports nothing.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""




START_SCENE = "NewStartScene"   # the screen GO-Map lives on; back from the map lands here


# GO-Map lands HERE instead of the map when the account's class is configured
# for a pretest in the CRM — a placement test that has to be taken before the
# map is reachable. NOT every new user: it depends on the parent class config,
# so two fresh accounts can behave differently (the user explained this on
# 2026-08-18). Nothing is broken when a run sees this scene.
PRETEST_SCENE = "PretestScene"


MAP_SCENE = "MapScene"


# Onboarding ends by dropping the guest into avatar customisation. 4.6.0 renamed
# the scene with the 3D avatar (measured live 2026-09-14); the old name is kept
# so an older build still matches.
AVATAR_SCENE = ("Avatar3DBuilderScene", "AvatarBuilderScene")


# --- Guest: play the accessible levels -------------------------------------
# A guest gets levels 1-5 (the 5th being the first exam). These helpers open a
# level, prove EVERY activity in it actually starts, and finish one — all by
# object name, and without AltTesterUtils, which may not exist in a guest
# session (its absence is what makes the account-flow helpers hang).
ACTIVITY_SELECTION_SCENE = "ActivitySelectionScene"


# The thumbs prove the activity list is back without waiting on a scene poll.
ACTIVITY_SELECTION_SCENE_MARKER = "ActivityThumb"
