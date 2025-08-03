import pytest
from Utilities.utilsdemo import solve_lesson_express
from Utilities.altdriver_utils import *
from Utilities.utilsdemo import *

def test_t1(altdriver):
    class_id = 7456
    lesson_range = range(0, 6)  # Lessons 0 to 5

    for lesson_num in lesson_range:
        print(f"\n===== Starting Lesson {lesson_num} =====")
        try:
            solve_lesson_express(altdriver, class_id, lesson_num)
            print(f"===== Lesson {lesson_num} Completed Successfully =====\n")
        except Exception as e:
            print(f"[ERROR] Failed to solve Lesson {lesson_num}: {e}")
