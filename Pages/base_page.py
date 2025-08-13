# Pages/base_page.py
from Utilities import utilsdemo

class BasePage:
    def __init__(self, driver):
        self.driver = driver

    # Expose common utils if needed
    def click_by_name(self, name):
        return utilsdemo.click_by_name(self.driver, name)

    def wait_for_name(self, name, timeout=None):
        return utilsdemo.wait_for_name(self.driver, name, timeout)
