from .base_page import BasePage
from Utilities import utilsdemo
from alttester import By
import time

class StartScreen(BasePage):
    def login(self, username, password):
        return utilsdemo.login(self.driver, username, password)

    def go_to_map(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("GO-Map")  # from BasePage
    def go_to_tasks(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("GO-Tasks")  # from BasePage

    def go_to_shop(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("GO-Avatar_Builder")  # from BasePage

    def go_to_daily_games(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("GO-Daily")  # from BasePage

    def go_to_dialogue(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("GO-Dialogue")  # from BasePage


    def go_to_competitions(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("GO-Competitions")  # from BasePage

    def go_to_wordlist(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("WordListButton")  # from BasePage


    def go_to_treasure_island(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("GO-Treasure_Island")  # from BasePage


    def write_activity_report(self, file_handle):
        # Your reporter expects a file handle `f`, not a path
        return utilsdemo.write_activity_report(file_handle)
