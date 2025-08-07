import pytest
import time
import logging

from alttester import By

from Utilities.utilsdemo import *
from Utilities.test_users import USE_SINGLE_USER, SINGLE_USER, ALL_USERS
from Utilities.utilsdemo import write_activity_report
from datetime import datetime
import os

logging.getLogger("alttester").setLevel(logging.CRITICAL)

# Dynamically decide which users to test
test_cases = [SINGLE_USER] if USE_SINGLE_USER else ALL_USERS

@pytest.mark.express
@pytest.mark.parametrize("user_case", test_cases)
def test_batch_lessons(altdriver, user_case):
    driver, platform_name = altdriver
    username = user_case['username']
    password = user_case['password']
    class_id = user_case['class_id']
    lesson_nums = user_case['lesson_nums']

    print(f"\n[TEST] Platform: {platform_name} | User: {username} | Class: {class_id}")

    try:
        login(driver, username, password)
        time.sleep(5)

        for lesson_num in lesson_nums:
            print(f"[{platform_name}] Solving Lesson {lesson_num}")
            try:
                solve_lesson_express(driver, class_id, lesson_num)
                activity_report.append({
                    "activity": f"Lesson-{lesson_num}",
                    "status": "Passed",
                    "duration": "N/A",
                    "error": "",
                    "platform": platform_name
                })
            except Exception as e:
                activity_report.append({
                    "activity": f"Lesson-{lesson_num}",
                    "status": "Failed",
                    "duration": "N/A",
                    "error": str(e),
                    "platform": platform_name
                })
                raise
    except Exception as login_error:
        print(f"[ERROR] Login failed for {username}: {login_error}")
        raise


@pytest.mark.sanity
def test_project(altdriver):
    driver, platform_name = altdriver
    username = SINGLE_USER['username']
    password = SINGLE_USER['password']
    class_id = SINGLE_USER['class_id']
    lesson_num = SINGLE_USER['lesson_nums'][1]  # Pick first lesson

    print(f"[TEST] Logging in {username} on {platform_name}")
    login(driver, username, password)
    time.sleep(3)

    # Click on the map button
    try:
        map_button = driver.find_object(By.NAME, "GO-Map")  # Confirm this name in AltTester Explorer
        map_button.click()  # Use .tap() instead of .click() in AltTester
        time.sleep(4)
        print("[INFO] Map button clicked successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to click map button: {e}")
        raise

    # Solve lesson express
    try:
        solve_lesson_express(driver, class_id, lesson_num)
        print(f"[INFO] Lesson {lesson_num} solved successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to solve lesson {lesson_num}: {e}")
        raise