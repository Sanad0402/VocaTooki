import time
import pytest
from alttester import By

from Pages.LoginPage import LoginPage
from Utilities import utilsdemo


_SETUP_DONE = False


@pytest.mark.sanity1
@pytest.mark.Start
class TestStartScreenNavigation:

    @pytest.fixture(autouse=True)
    def setup_once(self, altdriver, user):
        global _SETUP_DONE
        driver, _platform = altdriver

        if not _SETUP_DONE:
            # cleanup once: logout -> login -> wait 5 sec -> ensure GO-Map
            try:
                utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
                time.sleep(2)
            except Exception:
                pass

            login_page = LoginPage(driver)
            login_page.wait_until_open(timeout=25)

            login_page.login(user["username"], user["password"])
            time.sleep(5)

            driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=25)
            _SETUP_DONE = True

        else:
            # make sure we are on start screen before each test (no logout)
            # try a few times to find GO-Map, otherwise click back
            for _ in range(5):
                try:
                    driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=2)
                    break
                except Exception:
                    for back_name in ("BackButton", "GO-Back", "PrevButton", "PreviousButton", "NextButton"):
                        try:
                            driver.wait_for_object(By.NAME, back_name, enabled=True, timeout=2).click()
                            time.sleep(2)
                            break
                        except Exception:
                            pass

            driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=10)

    # -------------------------
    # One TC per scene
    # -------------------------

    def test_go_to_map_opens_map_scene(self, altdriver):
        time.sleep(5)
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "MapScene", f"Expected 'MapScene' but got '{current_scene}'"

        clicked = False
        for back_name in ("BackButton", "GO-Back", "PrevButton", "PreviousButton", "NextButton"):
            try:
                driver.wait_for_object(By.NAME, back_name, enabled=True, timeout=5).click()
                clicked = True
                time.sleep(2)
                break
            except Exception:
                pass
        assert clicked, "No Back/Prev/Next button found."

        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)

    def test_go_to_tasks_opens_task_manager_scene(self, altdriver):
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "GO-Tasks", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "TaskManager", f"Expected 'TaskManager' but got '{current_scene}'"

        # ✅ click Button BEFORE back
        driver.wait_for_object(By.NAME, "Button", enabled=True, timeout=10).click()
        time.sleep(1)

        # back
        clicked = False
        for back_name in ("BackButton", "prev", "PrevButton", "NextButton"):
            try:
                driver.wait_for_object(By.NAME, back_name, enabled=True, timeout=5).click()
                clicked = True
                time.sleep(2)
                break
            except Exception:
                pass
        assert clicked, "No Back/Prev/Next button found."

        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)

    def test_go_to_shop_opens_avatar_builder_scene(self, altdriver):
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "GO-Avatar_Builder", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "AvatarBuilderScene", f"Expected 'AvatarBuilderScene' but got '{current_scene}'"

        clicked = False
        for back_name in ("BackButton", "GO-Back", "PrevButton", "PreviousButton", "NextButton"):
            try:
                driver.wait_for_object(By.NAME, back_name, enabled=True, timeout=5).click()
                clicked = True
                time.sleep(2)
                break
            except Exception:
                pass
        assert clicked, "No Back/Prev/Next button found."

        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)

    def test_go_to_daily_games_opens_daily_games_selection_scene(self, altdriver):
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "GO-Daily", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "DailyGamesSelection", f"Expected 'DailyGamesSelection' but got '{current_scene}'"
        time.sleep(2)

        driver.wait_for_object(By.NAME, "prev", enabled=True, timeout=20).click()
        time.sleep(6)

        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)

    def test_go_to_dialogue_opens_dialogue_selection_scene(self, altdriver):
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "GO-Dialogue", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "DialogueSelectionScene", f"Expected 'DialogueSelectionScene' but got '{current_scene}'"

        clicked = False
        for back_name in ("BackButton", "GO-Back", "PrevButton", "PreviousButton", "NextButton"):
            try:
                driver.wait_for_object(By.NAME, back_name, enabled=True, timeout=5).click()
                clicked = True
                time.sleep(2)
                break
            except Exception:
                pass
        assert clicked, "No Back/Prev/Next button found."

        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)

    def test_go_to_competitions_opens_tournament_selection_scene(self, altdriver):
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "GO-Competitions", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "TournamentSelectionScene", f"Expected 'TournamentSelectionScene' but got '{current_scene}'"

        clicked = False
        for back_name in ("BackButton", "GO-Back", "PrevButton", "PreviousButton", "NextButton"):
            try:
                driver.wait_for_object(By.NAME, back_name, enabled=True, timeout=5).click()
                clicked = True
                time.sleep(2)
                break
            except Exception:
                pass
        assert clicked, "No Back/Prev/Next button found."

        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)

    def test_go_to_treasure_island_opens_treasure_island_scene(self, altdriver):
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "GO-Treasure_Island", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "TreasureIsland", f"Expected 'TreasureIsland' but got '{current_scene}'"

        clicked = False
        for back_name in ("BackButton", "GO-Back", "PrevButton", "PreviousButton", "NextButton"):
            try:
                driver.wait_for_object(By.NAME, back_name, enabled=True, timeout=6).click()
                clicked = True
                time.sleep(2)
                break
            except Exception:
                pass
        assert clicked, "No Back/Prev/Next button found."

        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)

    def test_go_to_audiobook_opens_audiobook_library_scene(self, altdriver):
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "GO-Audiobook", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "AudiobookLibraryScene", f"Expected 'AudiobookLibraryScene' but got '{current_scene}'"

        clicked = False
        for back_name in ("BackButton", "GO-Back", "PrevButton", "PreviousButton", "NextButton"):
            try:
                driver.wait_for_object(By.NAME, back_name, enabled=True, timeout=6).click()
                clicked = True
                time.sleep(2)
                break
            except Exception:
                pass
        assert clicked, "No Back/Prev/Next button found."

        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)

    def test_go_to_wordlist_opens_wordlist_scene(self, altdriver):
        driver, _platform = altdriver

        driver.wait_for_object(By.NAME, "WordListButton", enabled=True, timeout=20).click()
        time.sleep(6)

        current_scene = driver.get_current_scene()
        print("Current scene:", current_scene)
        assert current_scene == "WordListScene", f"Expected 'WordListScene' but got '{current_scene}'"

        time.sleep(2)

        driver.wait_for_object(By.NAME, "nextButton", enabled=True, timeout=20).click()
        time.sleep(6)



        back_scene = driver.get_current_scene()
        assert back_scene == "NewStartScene", f"Expected 'NewStartScene' after back, but got '{back_scene}'"
        driver.wait_for_object(By.NAME, "GO-Map", enabled=True, timeout=15)
