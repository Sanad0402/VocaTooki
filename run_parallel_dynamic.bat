@echo off
setlocal enabledelayedexpansion

:: =============================
:: Voca Tooki - Dynamic Parallel Test Runner
:: =============================

:: Define test configurations here
:: Each line: platform|app_id|device_id|test_file|marker (optional)

set CONFIGS[0]=WindowsEditor|13C50000|73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48|test_NavigateStartScene.py|sanity
set CONFIGS[1]=Android|com.vocatooki.app|0c3c8c9f254e1dc5880f9b27e048365e|test_batch_gameplay.py|express
set CONFIGS[2]=WebGL|WebGLAppId|YOUR_WEBGL_DEVICE_ID|test_users.py|dialogues
set CONFIGS[3]=WindowsBuild|com.vocatooki.build|YOUR_WINDOWS_BUILD_DEVICE_ID|test_users.py|exams

:: Loop through configs
set i=0
:loop
if defined CONFIGS[%i%] (
    for /f "tokens=1-5 delims=|" %%a in ("!CONFIGS[%i%]!") do (
        set PLATFORM=%%a
        set APP_ID=%%b
        set DEVICE_ID=%%c
        set TEST_FILE=%%d
        set MARKER=%%e

        set WINDOW_TITLE=!PLATFORM! - !TEST_FILE!

        echo [!PLATFORM!] Launching !TEST_FILE! with marker !MARKER!

        if defined MARKER (
            start "!WINDOW_TITLE!" cmd /k pytest -s !TEST_FILE! --platform=!PLATFORM! --app_id=!APP_ID! --device_instance_id=!DEVICE_ID! -m !MARKER!
        ) else (
            start "!WINDOW_TITLE!" cmd /k pytest -s !TEST_FILE! --platform=!PLATFORM! --app_id=!APP_ID! --device_instance_id=!DEVICE_ID!
        )
    )
    set /a i+=1
    goto loop
)

echo All test sessions started.
endlocal