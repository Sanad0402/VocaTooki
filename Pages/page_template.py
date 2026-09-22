# Pages/new_page.py
import time
from alttester import By

class NewPage:
    # ✅ change this to a UNIQUE object that exists only in this scene
    OPEN_ANCHOR = "NewPageAnchor"

    def __init__(self, driver):
        self.driver = driver

    def is_open(self) -> bool:
        try:
            self.driver.find_object(By.NAME, self.OPEN_ANCHOR)
            return True
        except Exception:
            return False

    def wait_until_open(self, timeout=20, poll=0.5):
        start = time.time()
        while time.time() - start < timeout:
            if self.is_open():
                return
            time.sleep(poll)
        raise AssertionError(f"[FAIL] NewPage not open. Missing anchor: {self.OPEN_ANCHOR}")
