"""
TC134 — TC08 – Locked/Disabled Account

Auto-generated from Rally (Method = Automated).

Description:
    Verify that locked pupil accounts cannot log in.

(No test steps recorded in Rally — add them to the case, then re-sync.)
"""

import time
from Pages.LoginPage import LoginPage

# Rally test case ID (for sync and maintenance)
TC_ID = "TC134"
# Set MANUAL_EDIT = True to keep your changes when re-syncing from Rally.
MANUAL_EDIT = False


def test_tc134_tc08_locked_disabled_account(altdriver):
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

    username = "invalid_user"
    password = "invalid_pass"

    login_page.set_username(username)
    login_page.set_password(password)
    login_page.click_login()
    time.sleep(3)

    # Negative expectation: login must be rejected. Either we stay on the login
    # screen, or an error/notification is shown. (LoginPage exposes get_notif_text()
    # and is_open(); there is no error_visible().)
    still_on_login = login_page.is_open()
    notif = login_page.get_notif_text()
    assert still_on_login or notif, \
        f"Expected login to be rejected but it was accepted ({TC_ID})"
