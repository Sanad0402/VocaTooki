@echo off
setlocal

echo ================================
echo  Starting Parallel Test Runner
echo ================================

REM ---- Unity Editor: Running express tests only ----
start "Unity Editor Test" cmd /k ^
    pytest -s ^
    --platform=WindowsEditor ^
    --app_id=13C50000 ^
    --device_instance_id=73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48 ^
    -m "express"

REM ---- Android: Running dialogues tests only ----
start "Android Dialogues" cmd /k ^
    pytest -s ^
    --platform=Android ^
    --app_id=com.vocatooki.app ^
    --device_instance_id=0c3c8c9f254e1dc5880f9b27e048365e ^
    -m "dialogues"

endlocal