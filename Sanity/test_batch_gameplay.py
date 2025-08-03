import time

import pytest
from alttester import By
from Utilities.utilsdemo import solve_lesson_express, login
import logging

logging.getLogger("alttester").setLevel(logging.CRITICAL)

CLASS_ID = 7456
LESSON_NUM = 3

def test_batch_run(altdriver):
    driver, platform_name = altdriver
    print(f"\n[TEST] Running batch on platform: {platform_name}")

    login(driver)
    time.sleep(5)


    print(f"[{platform_name}] Batch completed.")
