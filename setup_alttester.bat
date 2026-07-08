@echo off
REM ========================================================================
REM  AltTester MCP Setup Script
REM  Automates the setup and verification process
REM ========================================================================

setlocal enabledelayedexpansion

echo.
echo ========================================================================
echo           AltTester MCP Setup & Verification
echo ========================================================================
echo.

REM Colors and formatting
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "RESET=[0m"

REM ========================================================================
REM STEP 1: Check Python
REM ========================================================================
echo [STEP 1] Checking Python environment...
.venv\Scripts\python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('.venv\Scripts\python --version') do set PYTHON_VER=%%i
    echo   OK - Found !PYTHON_VER!
) else (
    echo   FAIL - Python not found
    goto :EOF
)

REM ========================================================================
REM STEP 2: Check pytest
REM ========================================================================
echo.
echo [STEP 2] Checking pytest...
.venv\Scripts\python -m pytest --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('.venv\Scripts\python -m pytest --version') do set PYTEST_VER=%%i
    echo   OK - !PYTEST_VER!
) else (
    echo   FAIL - pytest not found
    goto :EOF
)

REM ========================================================================
REM STEP 3: Check AltTester CLI
REM ========================================================================
echo.
echo [STEP 3] Checking AltTester CLI...
where alttester >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('alttester --version') do set ALTTESTER_VER=%%i
    echo   OK - !ALTTESTER_VER!
) else (
    echo   WARN - AltTester CLI not found
    echo.
    echo   Install AltTester:
    echo   1. Launch AltTester Desktop
    echo   2. Click "Download" button
    echo   3. Or: Settings ^> Configure AI Extension ^> Setup
    echo   4. Restart terminal after installing
    echo.
    echo   Then run this script again.
    echo.
    pause
    goto :EOF
)

REM ========================================================================
REM STEP 4: List registered games
REM ========================================================================
echo.
echo [STEP 4] Checking for registered games...
alttester apps --timeout 5 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   OK - Game found
    alttester apps --timeout 5
) else (
    echo   WARN - No game detected
    echo.
    echo   Make sure to:
    echo   1. Start your game with AltTester SDK enabled
    echo   2. Game must be listening on port 13000
    echo   3. Then run: alttester apps
    echo.
)

REM ========================================================================
REM STEP 5: Run verification script
REM ========================================================================
echo.
echo [STEP 5] Running setup verification...
echo.
.venv\Scripts\python verify_alttester_setup.py
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================================
    echo SUCCESS - All checks passed!
    echo ========================================================================
) else (
    echo.
    echo ========================================================================
    echo PARTIAL - Some checks need attention (see above)
    echo ========================================================================
)

REM ========================================================================
REM STEP 6: Instructions for next steps
REM ========================================================================
echo.
echo ========================================================================
echo NEXT STEPS - Follow these 3 commands in sequence:
echo ========================================================================
echo.
echo COMMAND 1 - Start MCP Server (keep this terminal open):
echo   alttester mcp
echo.
echo COMMAND 2 - Start your game (new terminal):
echo   (Launch your game with AltTester SDK enabled)
echo.
echo COMMAND 3 - Run tests (new terminal):
echo   cd C:\Users\sanad\PycharmProjects\Automation
echo   .venv\Scripts\python -m pytest Tests/test_alttester_mcp_example.py -v -s
echo.
echo ========================================================================
echo.
echo Press any key to exit...
pause >nul
