import pytest
import time
import logging
from Utilities.utilsdemo import login, solve_lesson_express, activity_report
from Utilities.test_users import USE_SINGLE_USER, SINGLE_USER, ALL_USERS

logging.getLogger("alttester").setLevel(logging.CRITICAL)

# Dynamically decide which users to test
test_cases = [SINGLE_USER] if USE_SINGLE_USER else ALL_USERS

@pytest.mark.express  # <-- Add this
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
