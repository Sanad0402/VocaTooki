import time
import inflect
from Utilities.utilsdemo import *

@pytest.mark.smoke

def test_09_san_map(altdriver):
    #click on play button
    time.sleep(4)
    play_button = altdriver.wait_for_object(By.NAME,"MapButton")
    play_button.click()
    time.sleep(5)

    #verify that the map scene opened
    actual_scene = altdriver.get_current_scene()
    expected_scene = 'MapScene'
    assert actual_scene == expected_scene


@pytest.mark.smoke
def test_10_san_first_lesson(altdriver):

    solve_lesson(altdriver,7456,1)



def test_exam_function(altdriver):
    solve_exam(altdriver, 8382, 2)

def test_solve_lesson_levels(altdriver):
    solve_lesson_levels(altdriver, 7456, 10)



def test_login_function(altdriver):

    login(altdriver, 'vt01274560005', '5262')

def test_solve_lesson_function(altdriver):
    solve_lesson(altdriver,7456 , 4)

def test_memory(altdriver):
    memory(altdriver)

for lesson_number in range(20, 25):  # 19 because range is exclusive at the end
    solve_lesson_express(altdriver, 7456, lesson_number)