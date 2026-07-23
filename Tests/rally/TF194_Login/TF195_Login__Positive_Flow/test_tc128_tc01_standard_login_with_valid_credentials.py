"""
TC128 — TC01 – Standard Login with Valid Credentials

Auto-generated from Rally test case.
Expected: Successful login and redirect to home screen.
"""

import time
from Pages.LoginPage import LoginPage
from Pages.StartScreen import StartScreen

# Rally test case ID (for sync and maintenance)
TC_ID = "TC128"
# Set MANUAL_EDIT = True to keep your changes when re-syncing from Rally.
MANUAL_EDIT = True


def test_tc128_tc01_standard_login_with_valid_credentials(altdriver):
    driver, _platform = altdriver
    login_page = LoginPage(driver)

    if not login_page.is_open():
        try:
            from Utilities import utilsdemo
            utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
            time.sleep(2)
        except Exception:
            pass

    login_page.wait_until_open(timeout=20)

    username = "vt010001"
    password = "4354"

    login_page.set_username(username)
    login_page.set_password(password)
    login_page.click_login()
    time.sleep(5)

    assert StartScreen(driver).is_present("GO-Map"), \
        f"Login failed: GO-Map not found after login ({TC_ID})"
