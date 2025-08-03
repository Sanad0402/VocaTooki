from Utilities.utilsdemo import solve_lesson_express, login

CLASS_ID = 7456
LESSONS = range(0, 6)  # Lessons 0-5

def test_batch_run(altdriver):
    driver, platform_name = altdriver
    print(f"\n[TEST] Running batch on platform: {platform_name}")

    login(driver)

    for lesson_num in LESSONS:
        print(f"[{platform_name}] Starting Lesson {lesson_num}")
        try:
            solve_lesson_express(driver, CLASS_ID, lesson_num)
            print(f"[{platform_name}] Lesson {lesson_num} completed successfully.")
        except Exception as e:
            print(f"[{platform_name}] [ERROR] Lesson {lesson_num} failed: {e}")

    print(f"[{platform_name}] Batch completed.\n")
