@echo off
setlocal

echo [Editor] Starting test on Unity Editor...
start "" cmd /k pytest Sanity/test_gameplay.py ^
    --platform=WindowsEditor ^
    --app_id=F6A0000 ^
    --device_instance_id=73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48

echo [Android] Starting test on Android device...
start "" cmd /k pytest Sanity/test_gameplay.py ^
    --platform=Android ^
    --app_id=86E60000 ^
    --device_instance_id=0c3c8c9f254e1dc5880f9b27e048365e

endlocal
