# Pages/map_page.py
from .base_page import BasePage
from Utilities import utilsdemo
from alttester import By
import time

DIFF_INDEX = {"easy": 0, "medium": 1, "hard": 2}

class MapPage(BasePage):
    def solve_lesson_express_hard(self, class_id, lesson_num):
        """Solve full lesson including all levels and the exam."""
        return utilsdemo.solve_lesson_express_hard(self.driver, class_id, lesson_num)

    def solve_lessons_express_hard(self, class_id, num_lessons, start_lesson=0):
        """Solve `num_lessons` lessons (hard express), starting at `start_lesson`."""
        return utilsdemo.solve_lessons_express_hard(self.driver, class_id, num_lessons, start_lesson)
    def solve_lesson(self, class_id, lesson_num):
        return utilsdemo.solve_lesson(self.driver, class_id, lesson_num)

    def solve_lesson_express(self, class_id, lesson_num):
        return utilsdemo.solve_lesson_express(self.driver, class_id, lesson_num)
    def solve_lesson_levels_express_hard(self, class_id, lesson_num):
        return utilsdemo.solve_lesson_levels_express_hard(self.driver, class_id, lesson_num)
    def solve_lesson_levels_express(self, class_id, lesson_num):
        return utilsdemo.solve_lesson_levels_express(self.driver, class_id, lesson_num)

    # NEW: navigate to a specific difficulty and solve only that level
    def run_single_level(self, class_id, level_idx, difficulty: str):
        difficulty = difficulty.lower()
        if difficulty not in DIFF_INDEX:
            raise ValueError(f"Unknown difficulty '{difficulty}'. Use one of: {list(DIFF_INDEX)}")

        # 1) navigate on the map exactly like your util does
        entered = utilsdemo.enter_to_level(
            self.driver, class_id, level_idx, type="lesson", difficulty=difficulty
        )
        if not entered:
            print(f"[WARN] No '{difficulty}' level found at map node {level_idx}; skipping.")
            return False

        try:
            # 2) run the level with the same engine your express flow uses
            utilsdemo.solve_level_express(self.driver, DIFF_INDEX[difficulty])
        finally:
            # 3) back to the map (same as your express flow)
            back_btn = self.driver.wait_for_object(By.NAME, "Back")
            back_btn.click()
            time.sleep(6)

        return True

    def write_activity_report(self, file_handle):
        # Your reporter expects a file handle `f`, not a path
        return utilsdemo.write_activity_report(file_handle)