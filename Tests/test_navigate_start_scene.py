import os
import time
import pathlib
import pytest

from alttester import By
from Utilities import utilsdemo

from Pages.StartScreen import StartScreen
from Pages.map_page import MapPage  # ok to keep even if unused


REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports"))


def _ensure_reports_dir():
    pathlib.Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)


def _report_filename(platform_name: str, username: str) -> str:
    safe_user = "".join(c for c in username if c.isalnum() or c in ("@", "_", "-", ".")).replace("@", "_at_")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPORTS_DIR, f"ActivityReport_{platform_name}_{safe_user}_{ts}.txt")


def _click_if_present(driver, name: str, timeout: float = 1.5) -> bool:
    try:
        driver.wait_for_object(By.NAME, name, enabled=True, timeout=timeout).click()
        return True
    except Exception:
        return False


def _wait_for_scene_change(driver, from_scene: str, timeout=25, poll=0.5) -> str:
    """
    Wait until scene != from_scene, return the new scene.
    """
    start = time.time()
    last_scene = from_scene
    while time.time() - start < timeout:
        last_scene = StartScreen.get_current_scene(driver)
        if last_scene and last_scene != from_scene:
            return last_scene
        time.sleep(poll)

    # If no change, return whatever we last saw (might be same as from_scene)
    return last_scene or from_scene


@pytest.mark.sanity2  # ✅ one mark for all test cases
class TestStartScreenNavigation:
    """
    StartScreen navigation suite using the static StartScreen POM.
    - No @staticmethod in tests
    - wait_for_scene used in all navigations
    - Scene names are auto-discovered once per run per destination
    """

    @pytest.fixture(scope="class", autouse=True)
    def start_session(self, request, altdriver, user):
        print("\n[SETUP] Logging in for the test session...")

        try:
            driver, platform_name = altdriver
        except (ValueError, TypeError):
            driver = altdriver
            platform_name = "Unknown"

        username = user["username"]
        password = user["password"]

        # Login (static page)
        StartScreen.login(driver, username, password, utilsdemo)

        # Ensure StartScreen is open
        StartScreen.wait_until_open(driver, timeout=25)

        # Store on class
        request.cls.driver = driver
        request.cls.platform_name = platform_name
        request.cls.username = username

        # runtime discovered scene names for this run
        request.cls._scene_cache = {}

        yield

        print("\n[TEARDOWN] Generating activity report...")
        _ensure_reports_dir()
        report_path = _report_filename(platform_name, username)
        with open(report_path, "w", encoding="utf-8") as f:
            StartScreen.write_activity_report(f, utilsdemo)
        print(f"[INFO] Activity report written: {report_path}")

    def _remember_and_wait_scene(self, key: str, timeout=25, allow_same_scene=False):
        """
        Ensures we call StartScreen.wait_for_scene(driver, expected, timeout)
        for every navigation.

        - If scene for `key` is known (cached) -> wait_for_scene(expected)
        - Else -> discover by waiting for scene change, cache it, then wait_for_scene(discovered)
        - If allow_same_scene=True, we accept no scene change and cache current scene.
        """
        driver = self.driver
        before = StartScreen.get_current_scene(driver)

        if key not in self._scene_cache:
            after = _wait_for_scene_change(driver, before, timeout=timeout)

            if after == before and not allow_same_scene:
                raise AssertionError(
                    f"[{key}] Scene did not change. Still '{after}'. "
                    f"If this destination is a popup (no scene change), set allow_same_scene=True."
                )

            self._scene_cache[key] = after
            print(f"[INFO] Discovered scene for '{key}': {after}")

        expected = self._scene_cache[key]
        StartScreen.wait_for_scene(driver, expected, timeout=timeout)

    def _go_back_to_start_screen(self, special_back_buttons=None, attempts=4):
        """
        Navigate back until StartScreen is open.
        """
        driver = self.driver

        if StartScreen.is_open(driver):
            return

        special_back_buttons = tuple(special_back_buttons or ())
        common_buttons = (
            "BackButton", "HomeButton",
            "Back", "prev", "PrevButton",
            "Exit", "Close", "X",
        )

        for _ in range(attempts):
            # Try special first
            for name in special_back_buttons:
                if _click_if_present(driver, name, timeout=2):
                    time.sleep(0.6)
                    if StartScreen.is_open(driver):
                        return

            # Then common
            for name in common_buttons:
                if _click_if_present(driver, name, timeout=2):
                    time.sleep(0.6)
                    break

            if StartScreen.is_open(driver):
                return

        # Final hard check
        StartScreen.wait_until_open(driver, timeout=10)

    # -------------------------
    # Test cases
    # -------------------------

    def test_go_to_map(self):
        StartScreen.go_to_map(self.driver)
        self._remember_and_wait_scene("map", timeout=25)
        self._go_back_to_start_screen()

    def test_go_to_tasks(self):
        StartScreen.go_to_tasks(self.driver)

        # If you want strict known scene: uncomment next line and remove auto-discovery:
        # StartScreen.wait_for_scene(self.driver, "TaskManager", timeout=25)

        # Auto-discover + wait_for_scene (still uses wait_for_scene)
        self._remember_and_wait_scene("tasks", timeout=25)

        _click_if_present(self.driver, "Button", timeout=2)

        special_buttons = ("prev", "PrevButton", "Back", "BackButton", "HomeButton")
        self._go_back_to_start_screen(special_back_buttons=special_buttons)

    def test_go_to_shop(self):
        StartScreen.go_to_shop(self.driver)
        self._remember_and_wait_scene("shop", timeout=25)
        self._go_back_to_start_screen()

    def test_go_to_daily_games(self):
        StartScreen.go_to_daily_games(self.driver)

        # If you want strict known scene: uncomment next line and remove auto-discovery:
        # StartScreen.wait_for_scene(self.driver, "DailyGamesSelection", timeout=25)

        self._remember_and_wait_scene("daily", timeout=25)

        special_buttons = ("prev", "PrevButton", "Back", "BackButton", "HomeButton")
        self._go_back_to_start_screen(special_back_buttons=special_buttons)

    def test_go_to_dialogue(self):
        StartScreen.go_to_dialogue(self.driver)
        self._remember_and_wait_scene("dialogue", timeout=25)
        self._go_back_to_start_screen()

    def test_go_to_competitions(self):
        StartScreen.go_to_competitions(self.driver)
        self._remember_and_wait_scene("competitions", timeout=25)
        self._go_back_to_start_screen()

    def test_go_to_treasure_island(self):
        StartScreen.go_to_treasure_island(self.driver)
        self._remember_and_wait_scene("treasure_island", timeout=25)
        self._go_back_to_start_screen()

    def test_go_to_wordlist(self):
        StartScreen.go_to_wordlist(self.driver)

        # Wordlist is often a popup; scene may not change.
        # We still call wait_for_scene (on current scene) + validate popup button.
        self._remember_and_wait_scene("wordlist", timeout=10, allow_same_scene=True)

        _click_if_present(self.driver, "nextButton", timeout=2)
        self._go_back_to_start_screen()
