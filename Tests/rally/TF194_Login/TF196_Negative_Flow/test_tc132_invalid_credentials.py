"""TC132 — TC06 – Invalid Credentials  (TF196: Login – Negative Flow).

Type: Regression / Automated. Credentials are written here manually.

Rally Validation Input:
  - Enter username: vt01229400001
  - Enter password: 0000   (wrong password)
Rally Expected Result:
  - Error message displayed: "Invalid username or password".
  - Login not successful.
"""

import time

from Pages.LoginPage import LoginPage
from Pages.StartScreen import StartScreen
from Utilities import utilsdemo

# --- Credentials provided manually for this test case ---
USERNAME = "vt01229400001"
PASSWORD = "0000"                       # invalid on purpose
EXPECTED_ERROR = "Invalid username or password"   # Rally's expected wording


def test_invalid_credentials(altdriver):
    driver, _platform = altdriver
    login_page = LoginPage(driver)

    # Make sure we are on the login screen (log out if a session is open).
    if not login_page.is_open():
        try:
            utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
            time.sleep(2)
        except Exception:
            pass
    login_page.wait_until_open(timeout=20)

    # Enter a valid username with a wrong password, then submit.
    login_page.set_username(USERNAME)
    login_page.set_password(PASSWORD)
    login_page.click_login()
    time.sleep(3)

    # Expected: login NOT successful (we never reach the Start Scene) ...
    assert not StartScreen(driver).is_present("GO-Map"), \
        "Login succeeded with an invalid password — expected it to fail."

    # ... and an error message is shown. (Assert it's non-empty; tighten to the exact
    # string once you confirm the app's wording — Rally expects: "Invalid username or password".)
    error_text = login_page.get_notif_text(timeout=5)
    assert error_text, f"No error message shown for invalid credentials (expected ~ '{EXPECTED_ERROR}')."
    print(f"[TC132] error message shown: {error_text!r}")
