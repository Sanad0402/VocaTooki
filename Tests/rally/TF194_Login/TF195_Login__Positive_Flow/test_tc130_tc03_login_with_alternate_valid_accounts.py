"""
TC130 — TC03 – Login with Alternate Valid Accounts

Auto-generated from Rally (Method = Automated).

Description:
    Validate that the system allows successful login using different valid pupil accounts. This ensures login functionality is consistent across multiple pupils and not limited to a single user credential.

(No test steps recorded in Rally — add them to the case, then re-sync.)
"""

import time
import pytest
from Pages.LoginPage import LoginPage
from Pages.StartScreen import StartScreen

# Rally test case ID (for sync and maintenance)
TC_ID = "TC130"
# Set MANUAL_EDIT = True to keep your changes when re-syncing from Rally.
MANUAL_EDIT = False


@pytest.mark.stub
@pytest.mark.skip(reason="TC130: no credentials on the Rally case. Add Username/Password to the case, then re-sync.")
def test_tc130_tc03_login_with_alternate_valid_accounts(altdriver):
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

    username = "CHANGE_ME"
    password = ""

    login_page.set_username(username)
    login_page.set_password(password)
    login_page.click_login()
    time.sleep(5)

    assert StartScreen(driver).is_present("GO-Map"), \
        f"Login failed: GO-Map not found after login ({TC_ID})"
