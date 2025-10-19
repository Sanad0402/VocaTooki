import os
import time
import pathlib
import pytest

# Assuming these imports point to your project's structure
from data.test_users import DEFAULT_CLASS_ID
from Pages.StartScreen import StartScreen
from Pages.map_page import MapPage  # ok to keep even if unused

# --- Constants and Helper Functions ---

REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports"))


def _ensure_reports_dir():
    """Ensures the report directory exists."""
    pathlib.Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)


def _report_filename(platform_name: str, username: str) -> str:
    """Creates a safe and unique filename for the report."""
    safe_user = "".join(c for c in username if c.isalnum() or c in ("@", "_", "-", ".")).replace("@", "_at_")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPORTS_DIR, f"ActivityReport_{platform_name}_{safe_user}_{ts}.txt")


# --- Test Suite ---

@pytest.mark.sanity1
class TestStartScreenNavigation:
    """
    Test suite for navigating to all main areas from the StartScreen.
    Login is performed once before all tests, and the report is generated
    once after all tests complete, using a class-scoped fixture.
    """

    @pytest.fixture(scope="class", autouse=True)
    def session_setup_and_teardown(self, altdriver, user):
        """
        A class-scoped fixture that handles setup (login) and teardown (reporting).

        - SETUP: Performs login once before any test in this class runs.
        - YIELD: Passes the initialized StartScreen object to each test.
        - TEARDOWN: Generates the activity report after all tests are done.
        """
        # --- SETUP (Runs once before all tests in this class) ---
        print("\n[SETUP] Logging in for the test session...")
        try:
            driver, platform_name = altdriver
        except (ValueError, TypeError):
            driver = altdriver
            platform_name = "Unknown"

        username = user["username"]
        password = user["password"]

        start_screen = StartScreen(driver)
        start_screen.login(username, password)
        time.sleep(2)  # Wait for login to complete and animations to settle

        # The 'yield' keyword passes control to the tests.
        # We pass any objects the tests might need.
        yield start_screen, platform_name, username

        # --- TEARDOWN (Runs once after the last test in this class) ---
        print("\n[TEARDOWN] Generating activity report...")
        _ensure_reports_dir()
        report_path = _report_filename(platform_name, username)
        with open(report_path, "w", encoding="utf-8") as f:
            start_screen.write_activity_report(f)

        print(f"[INFO] Activity report written: {report_path}")

    def _go_back_to_start_screen(self, start_page: StartScreen, special_back_buttons=None):
        """Helper to reliably navigate back to the StartScreen to reset state."""
        # First, try any screen-specific back buttons
        if special_back_buttons:
            for name in special_back_buttons:
                try:
                    start_page.click_by_name(name)
                    time.sleep(2)
                    return  # Exit after successful click
                except Exception:
                    continue  # Try the next button name

        # If those fail, try the default back/home buttons
        try:
            start_page.click_by_name("BackButton")
        except Exception:
            try:
                start_page.click_by_name("HomeButton")
            except Exception:
                print("[WARN] No standard back/home button was found on this screen.")
        time.sleep(2)

    # --- Individual Test Cases ---

    def test_go_to_map(self, session_setup_and_teardown):
        start, _, _ = session_setup_and_teardown
        start.go_to_map()
        time.sleep(3)
        # Add assertions here if needed, e.g., assert start.get_current_scene() == "MapScene"
        self._go_back_to_start_screen(start)

    def test_go_to_tasks(self, session_setup_and_teardown):
        start, _, _ = session_setup_and_teardown
        start.go_to_tasks()
        time.sleep(3)
        # Scene-specific tweak for Tasks popup
        try:
            start.click_by_name("Button")
            time.sleep(1)
        except Exception:
            print("[WARN] Tasks popup 'Button' not found")

        # Task manager has unique back buttons
        special_buttons = ("prev", "PrevButton", "Back", "BackButton", "HomeButton")
        self._go_back_to_start_screen(start, special_back_buttons=special_buttons)

    def test_go_to_shop(self, session_setup_and_teardown):
        start, _, _ = session_setup_and_teardown
        start.go_to_shop()
        time.sleep(3)
        self._go_back_to_start_screen(start)

    def test_go_to_daily_games(self, session_setup_and_teardown):
        start, _, _ = session_setup_and_teardown
        start.go_to_daily_games()
        time.sleep(3)
        # Daily games also has unique back buttons
        special_buttons = ("prev", "PrevButton", "Back", "BackButton", "HomeButton")
        self._go_back_to_start_screen(start, special_back_buttons=special_buttons)

    def test_go_to_dialogue(self, session_setup_and_teardown):
        start, _, _ = session_setup_and_teardown
        start.go_to_dialogue()
        time.sleep(3)
        self._go_back_to_start_screen(start)

    def test_go_to_competitions(self, session_setup_and_teardown):
        start, _, _ = session_setup_and_teardown
        start.go_to_competitions()
        time.sleep(3)
        self._go_back_to_start_screen(start)

    def test_go_to_treasure_island(self, session_setup_and_teardown):
        start, _, _ = session_setup_and_teardown
        start.go_to_treasure_island()
        time.sleep(3)
        self._go_back_to_start_screen(start)

    def test_go_to_wordlist(self, session_setup_and_teardown):
        start, _, _ = session_setup_and_teardown
        start.go_to_wordlist()
        time.sleep(3)
        # Scene-specific tweak for WordList popup
        try:
            start.click_by_name("nextButton")  # case-sensitive
            time.sleep(1)
        except Exception:
            print("[WARN] WordList 'nextButton' not found")
        self._go_back_to_start_screen(start)