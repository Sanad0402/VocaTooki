"""TC128 — TC01 – Standard Login with Valid Credentials  (TF195: Login – Positive Flow).

Real pytest test. The credentials are written **here, manually** (not taken from
data/test_users.py, fixtures, or the suite JSON). The only thing injected is the AltDriver,
via the session ``altdriver`` fixture in conftest.py.

Rally steps: launch app → login screen → enter username/password → click Login.
Expected: authenticated and redirected to the Start Scene (Home) — GO-Map present.
"""

import time

from Pages.LoginPage import LoginPage
from Pages.StartScreen import StartScreen
from Utilities import utilsdemo

# --- Credentials provided manually for this test case ---
USERNAME = "vt01229400001"
PASSWORD = "0391"


def test_standard_login(altdriver):
    driver, _platform = altdriver
    login_page = LoginPage(driver)

    # Navigate to the login screen (log out first if a session is already open).
    if not login_page.is_open():
        try:
            utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
            time.sleep(2)
        except Exception:
            pass
    login_page.wait_until_open(timeout=20)

    # Enter valid credentials and submit.
    login_page.set_username(USERNAME)
    login_page.set_password(PASSWORD)
    login_page.click_login()
    time.sleep(5)

    # Expected result: authenticated and on the Start Scene (GO-Map present).
    assert StartScreen(driver).is_present("GO-Map"), \
        "Login did not reach the Start Scene (GO-Map not found) — authentication failed."
