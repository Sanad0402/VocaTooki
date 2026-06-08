"""TC131 — TC04 – UX/UI Validation  (TF195: Login – Positive Flow).

CONTINUATION test — it does NOT log in. It reuses the session that TC128
(Standard Login) established earlier in the SAME run, and just validates the
Start Scene (Home) UI. Run it together with TC128, in order; running it on its
own will fail because nobody is logged in yet.

Why this works: the runner executes all selected cases in one pytest process, and
the `altdriver` fixture is session-scoped — so the app stays open and logged in
between test cases.
"""

from Pages.StartScreen import StartScreen

# Home-page controls expected to be present once authenticated.
EXPECTED_CONTROLS = ["GO-Map", "GO-Tasks", "GO-Daily"]


def test_ux_ui_validation(altdriver):
    driver, _platform = altdriver
    start = StartScreen(driver)

    # No login here on purpose — continue from where TC128 left off.
    assert start.is_present("GO-Map"), (
        "Not on the Start Scene — run TC131 after TC128 in the same run "
        "(this continuation test does not log in by itself).")

    for name in EXPECTED_CONTROLS:
        assert start.is_present(name), f"Expected Home-page control '{name}' to be visible."
