@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo     AltTester MCP Setup
echo ========================================
echo.

REM Check Python
echo [1] Checking Python...
.venv\Scripts\python --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Python not found
    goto :EOF
)
echo [OK] Python found

REM Check pytest
echo [2] Checking pytest...
.venv\Scripts\python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] pytest not found
    goto :EOF
)
echo [OK] pytest found

REM Check AltTester
echo [3] Checking AltTester CLI...
where alttester >nul 2>&1
if errorlevel 1 (
    echo [WARN] AltTester CLI not found
    echo.
    echo Install AltTester:
    echo   1. Launch AltTester Desktop
    echo   2. Click "Download" button
    echo   3. Or: Settings ^> Configure AI Extension ^> Setup
    echo   4. Restart this terminal after installing
    echo   5. Re-run this script
    echo.
    pause
    goto :EOF
)
echo [OK] AltTester CLI found

echo.
echo ========================================
echo Next Steps:
echo ========================================
echo.
echo Terminal 1 (Keep Open):
echo   alttester mcp
echo.
echo Terminal 2 (Different):
echo   cd %cd%
echo   .venv\Scripts\python -m pytest Tests\test_alttester_mcp_example.py -v -s
echo.
echo Terminal 3 (Your Game):
echo   Launch your game with AltTester SDK
echo.
echo ========================================
echo.
pause
