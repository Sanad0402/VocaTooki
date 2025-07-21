import time
import inflect
from Utilities.utilsdemo import *
from Utilities.altdriver_utils import *



def test_solve_lesson_express(altdriver):

    for lesson_number in range(1, 2):  # 19 because range is exclusive at the end
        solve_lesson_express(altdriver, 8821, lesson_number)