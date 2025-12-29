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
    WORDLIST_BUTTON = "WordListButton"
    GO_TREASURE_ISLAND = "GO-Treasure_Island"

    OPEN_ANCHOR = GO_MAP

    # -------------------------
    # Presence / screen helpers
    # -------------------------
    @staticmethod
    def is_present(driver, name: str) -> bool:
        try:
            driver.find_object(By.NAME, name)
            return True
        except Exception:
            return False

    @staticmethod
    def is_open(driver) -> bool:
        return StartScreen.is_present(driver, StartScreen.OPEN_ANCHOR)

    @staticmethod
    def wait_until_open(driver, timeout=15, poll=0.5):
        start = time.time()
        while time.time() - start < timeout:
            if StartScreen.is_open(driver):
                return
            time.sleep(poll)
        raise AssertionError("StartScreen did not appear (GO-Map not found).")

    # -------------------------
    # Scene helpers
    # -------------------------
    @staticmethod
    def get_current_scene(driver) -> str:
        try:
            return driver.get_current_scene()
        except Exception:
            return ""

    @staticmethod
    def wait_for_scene(driver, expected_scene: str, timeout=20, poll=0.5):
        start = time.time()
        last_scene = ""
        while time.time() - start < timeout:
            last_scene = StartScreen.get_current_scene(driver)
            if last_scene == expected_scene:
                return
            time.sleep(poll)

        raise AssertionError(
            f"Expected scene '{expected_scene}' but got '{last_scene}' after {timeout}s"
        )

    # -------------------------
    # Login + click helpers
    # -------------------------
    @staticmethod
    def login(driver, username: str, password: str, utilsdemo):
        if utilsdemo is None:
            raise RuntimeError("utilsdemo was not provided to StartScreen.login().")
        return utilsdemo.login(driver, username, password)

    @staticmethod
    def _tap(driver, obj_name: str, timeout=10):
        driver.wait_for_object(By.NAME, obj_name, enabled=True, timeout=timeout).click()

    # -------------------------
    # Navigation actions
    # -------------------------
    @staticmethod
    def go_to_map(driver):
        StartScreen.wait_until_open(driver)
        StartScreen._tap(driver, StartScreen.GO_MAP)

    @staticmethod
    def go_to_tasks(driver):
        StartScreen.wait_until_open(driver)
        StartScreen._tap(driver, StartScreen.GO_TASKS)

    @staticmethod
    def go_to_shop(driver):
        StartScreen.wait_until_open(driver)
        StartScreen._tap(driver, StartScreen.GO_SHOP)

    @staticmethod
    def go_to_daily_games(driver):
        StartScreen.wait_until_open(driver)
        StartScreen._tap(driver, StartScreen.GO_DAILY)

    @staticmethod
    def go_to_dialogue(driver):
        StartScreen.wait_until_open(driver)
        StartScreen._tap(driver, StartScreen.GO_DIALOGUE)

    @staticmethod
    def go_to_competitions(driver):
        StartScreen.wait_until_open(driver)
        StartScreen._tap(driver, StartScreen.GO_COMPETITIONS)

    @staticmethod
    def go_to_wordlist(driver):
        StartScreen.wait_until_open(driver)
        StartScreen._tap(driver, StartScreen.WORDLIST_BUTTON)

    @staticmethod
    def go_to_treasure_island(driver):
        StartScreen.wait_until_open(driver)
        StartScreen._tap(driver, StartScreen.GO_TREASURE_ISLAND)

    # -------------------------
    # Report hook
    # -------------------------
    @staticmethod
    def write_activity_report(file_handle, utilsdemo):
        if utilsdemo is None:
            raise RuntimeError("utilsdemo was not provided to StartScreen.write_activity_report().")
        return utilsdemo.write_activity_report(file_handle)
