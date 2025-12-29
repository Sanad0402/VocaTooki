import time
import pytest
from alttester import By

from Pages.StartScreen import StartScreen
from Pages.LoginPage import LoginPage
from Utilities import utilsdemo


@pytest.mark.login
class TestLoginSimple:

    def _get_driver(self, altdriver):
        """
        Your fixture returns (driver, platform).
        This helper keeps it beginner-safe.
        """
        driver, _platform = altdriver
        return driver

    def _is_present(self, driver, name: str) -> bool:
        try:
            driver.find_object(By.NAME, name)
            return True
        except Exception:
            return False

    def _assert_start_screen(self, driver):
        """
        After successful login, GO-Map should exist.
        """
        assert self._is_present(driver, "GO-Map"), "GO-Map not found (login probably failed)."

    def _ensure_login_screen(self, driver):
        """
        Full fix for your question:
        - If we are NOT on login screen, call Logout (AltTesterUtils) to return to login screen.
        - Then wait until login screen is visible.
        """
        login_page = LoginPage(driver)

        if not login_page.is_open():
            # This is the line you asked about:
            # It is needed when you're not sure the app is on login screen.
            try:
                utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
                time.sleep(2)
            except Exception:
                # If Logout fails for any reason, we still try to wait for login screen
                pass

        login_page.wait_until_open(timeout=15)
        return login_page

    def _click_go_map(self, driver):
        """
        Click GO-Map button to enter the map scene.
        """
        time.sleep(10)
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True).click()
        time.sleep(2)

    def test_login_valid_user(self, altdriver, user):
        driver = self._get_driver(altdriver)

        login_page = self._ensure_login_screen(driver)

        # Login
        login_page.login(user["username"], user["password"])
        time.sleep(5)

        # Verify success (GO-Map exists)
        self._assert_start_screen(driver)

        # Click GO-Map
        self._click_go_map(driver)
        time.sleep(2)

        # ✅ Assert we are now in MapScene
        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "MapScene", f"Expected MapScene, but got {current_scene}"

        # Cleanup
        utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
        time.sleep(2)
        self._ensure_login_screen(driver)

    def test_login_invalid_password_stays_on_login(self, altdriver, user):
        """
        Negative test:
        1) Ensure we are on login screen
        2) Enter valid username + wrong password
        3) Click login
        4) Verify we stayed on login screen
        5) Verify we did NOT reach start screen (GO-Map must NOT exist)
        6) Read the error text from notifText and verify it is not empty
        """
        driver = self._get_driver(altdriver)

        # 1) Make sure we are on login screen
        login_page = self._ensure_login_screen(driver)

        # 2-3) Try login with wrong password
        login_page.set_username(user["username"])
        login_page.set_password("wrong_password_123")
        login_page.click_login()
        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "NewStartScene", f"Expected NewStartScene, but got {current_scene}"


        # 4) Wait a bit for the error message to appear
        time.sleep(2)

        # Still on login screen (fields still exist)
        login_page.wait_until_open(timeout=20)

        # 5) Verify we did NOT reach start screen
        assert  self._is_present(driver, "GO-Map"), "Login succeeded even with wrong password!"

        # 6) Read notifText and verify there is an error message
        error_text = login_page.get_notif_text(timeout=5)
        print("notifText message:", error_text)
        assert error_text ==  "Failed to login, Incorrect Credentials"

    def test_login_empty_username(self, altdriver, user):
        """
        Negative test: Username is empty
        Steps:
        1) Ensure login screen
        2) Leave username empty
        3) Enter password
        4) Click login
        5) Verify we stay on login screen
        6) Verify error message (notifText) is shown (if your app shows it)
        """
        driver = self._get_driver(altdriver)
        login_page = self._ensure_login_screen(driver)

        # Username empty + valid password
        login_page.set_username("")  # empty
        login_page.set_password(user["password"])
        login_page.click_login()
        time.sleep(2)


        # Validate notif text
        error_text = login_page.get_notif_text(timeout=3)
        print("notifText:", repr(error_text))
        assert error_text == "One of the fields is empty.", "Expected error message in notifText for empty username."

    def test_login_empty_password(self, altdriver, user):
        """
        Negative test: Password is empty
        Steps:
        1) Ensure login screen
        2) Enter username
        3) Leave password empty
        4) Click login
        5) Verify we stay on login screen
        6) Verify error message (notifText) is shown (if your app shows it)
        """
        driver = self._get_driver(altdriver)
        login_page = self._ensure_login_screen(driver)

        # Valid username + empty password
        login_page.set_username(user["username"])
        login_page.set_password("")  # empty
        login_page.click_login()
        time.sleep(2)

        # Optional: validate notif text
        error_text = login_page.get_notif_text(timeout=3)
        print("notifText:", repr(error_text))
        assert error_text == "One of the fields is empty.", "Expected error message in notifText for empty username."
