from .base_page import BasePage
from Utilities import utilsdemo

class StartScreen(BasePage):
    def login(self, username, password):
        return utilsdemo.login(self.driver, username, password)

    def go_to_map(self):
        """Tap the GO-Map object after login."""
        self.click_by_name("GO-Map")  # from BasePage
