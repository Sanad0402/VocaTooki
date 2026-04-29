import time
from alttester import By


class StartScreen:
    # ---- Unity object names (buttons) ----
    GO_MAP = "GO-Map"
    GO_TASKS = "GO-Tasks"
    GO_SHOP = "GO-Avatar_Builder"
    GO_DAILY = "GO-Daily"
    GO_DIALOGUE = "GO-Dialogue"
    GO_COMPETITIONS = "GO-Competitions"
    GO_TREASURE_ISLAND = "GO-Treasure_Island"
    GO_AUDIOBOOK = "GO-Audiobook"
    WORDLIST_BUTTON = "WordListButton"

    OPEN_ANCHOR = GO_MAP

    # Common back button names (tries these in order)
    BACK_BUTTON_CANDIDATES = [
        "BackButton",
        "GO-Back",
        "BtnBack",
        "Back",
        "ButtonBack",
        "Back_Arrow",
        "prev",
        "nextButton"
    ]

    def __init__(self, driver, utilsdemo=None):
        self.driver = driver
        self.utilsdemo = utilsdemo

    # -------------------------
    # Presence / screen helpers
    # -------------------------
    def is_present(self, name: str) -> bool:
        try:
            self.driver.find_object(By.NAME, name)
            return True
        except Exception:
            return False

    def is_open(self) -> bool:
        return self.is_present(self.OPEN_ANCHOR)

    def wait_until_open(self, timeout=15, poll=0.5):
        start = time.time()
        while time.time() - start < timeout:
            if self.is_open():
                return
            time.sleep(poll)
        raise AssertionError("StartScreen did not appear (GO-Map not found).")

    # -------------------------
    # Scene helpers
    # -------------------------
    def get_current_scene(self) -> str:
        try:
            return self.driver.get_current_scene()
        except Exception:
            return ""

    def wait_for_scene(self, expected_scene: str, timeout=20, poll=0.5):
        start = time.time()
        last_scene = ""
        while time.time() - start < timeout:
            last_scene = self.get_current_scene()
            if last_scene == expected_scene:
                return
            time.sleep(poll)
        raise AssertionError(
            f"Expected scene '{expected_scene}' but got '{last_scene}' after {timeout}s"
        )

    # -------------------------
    # Login + click helpers
    # -------------------------
    def login(self, username: str, password: str):
        if self.utilsdemo is None:
            raise RuntimeError(
                "utilsdemo was not provided to StartScreen. "
                "Create StartScreen(driver, utilsdemo=utilsdemo)."
            )
        return self.utilsdemo.login(self.driver, username, password)

    def _tap(self, obj_name: str, timeout=10):
        self.driver.wait_for_object(By.NAME, obj_name, enabled=True, timeout=timeout).click()

    # -------------------------
    # Navigation actions
    # -------------------------
    def go_to_map(self):
        self.wait_until_open()
        self._tap(self.GO_MAP)

    def go_to_tasks(self):
        self.wait_until_open()
        self._tap(self.GO_TASKS)

    def go_to_shop(self):
        self.wait_until_open()
        self._tap(self.GO_SHOP)

    def go_to_daily_games(self):
        self.wait_until_open()
        self._tap(self.GO_DAILY)

    def go_to_dialogue(self):
        self.wait_until_open()
        self._tap(self.GO_DIALOGUE)

    def go_to_competitions(self):
        self.wait_until_open()
        self._tap(self.GO_COMPETITIONS)

    def go_to_wordlist(self):
        self.wait_until_open()
        self._tap(self.WORDLIST_BUTTON)

    def go_to_treasure_island(self):
        self.wait_until_open()
        self._tap(self.GO_TREASURE_ISLAND)

    def go_to_audiobook(self):
        self.wait_until_open()
        self._tap(self.GO_AUDIOBOOK)

    # -------------------------
    # Back helper (flexible back button detection)
    # -------------------------
    def tap_back(self, timeout=10):
        """
        Try multiple back button names.
        Returns True if back button was found and clicked.
        """
        for name in self.BACK_BUTTON_CANDIDATES:
            try:
                if self.is_present(name):
                    self._tap(name, timeout=timeout)
                    return True
            except Exception:
                continue

        raise AssertionError(
            f"Back button not found. Tried: {', '.join(self.BACK_BUTTON_CANDIDATES)}. "
            "Update BACK_BUTTON_CANDIDATES in StartScreen to match your Unity back button."
        )

    # -------------------------
    # Report hook (optional)
    # -------------------------
    def write_activity_report(self, file_handle):
        if self.utilsdemo is None:
            raise RuntimeError(
                "utilsdemo was not provided to StartScreen. "
                "Create StartScreen(driver, utilsdemo=utilsdemo)."
            )
        return self.utilsdemo.write_activity_report(file_handle)

    def go_to_new_page(self, timeout=25):
        # click(s) needed to reach the new scene
        self.driver.wait_for_object(By.NAME, self.GO_TASKS, enabled=True, timeout=timeout).click()
        # if you need more clicks, add them here:
        # self.driver.wait_for_object(By.NAME, "Button2", enabled=True, timeout=timeout).click()
        # self.driver.wait_for_object(By.NAME, "Button3", enabled=True, timeout=timeout).click()

        from Pages.new_page import NewPage
        page = NewPage(self.driver)
        page.wait_until_open(timeout=timeout)
        return page