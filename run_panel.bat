@echo off
REM ============================================================
REM  Voca Tooki - Test Runner launcher
REM  Double-click this file to start the runner panel and open
REM  it in your browser at http://127.0.0.1:5000
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [ERROR] Virtual environment not found at %PY%
    echo Create it first:  python -m venv .venv ^&^& .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

REM If the panel is already listening on port 5000, just open the browser.
netstat -ano | findstr ":5000 " | findstr LISTENING >nul
if %errorlevel%==0 (
    echo Runner already running on http://127.0.0.1:5000
    start "" http://127.0.0.1:5000/
    endlocal
    exit /b 0
)

echo Starting Voca Tooki Test Runner...
REM Output goes to panel.log / panel.err.log instead of a console window.
REM A console window is a trap on Windows: one click inside it turns on
REM QuickEdit text selection, which SUSPENDS all writes — every Flask thread
REM then freezes mid-request and the page loads forever. On a startup crash,
REM read panel.err.log for the traceback.
start "Voca Tooki Runner" /min cmd /c ""%PY%" -u run_panel.py 1>panel.log 2>panel.err.log"

REM Wait until the server is actually listening (up to ~20s) before opening the
REM browser, so a slow cold start doesn't show "can't reach this page".
echo Waiting for the server to come up...
set "UP="
for /L %%i in (1,1,20) do (
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr ":5000 " | findstr LISTENING >nul
    if !errorlevel!==0 (
        set "UP=1"
        goto :ready
    )
)

:ready
if defined UP (
    echo Server is up.
    start "" http://127.0.0.1:5000/
) else (
    echo [ERROR] The server did not start within 20 seconds.
    echo Check panel.err.log for the Python error/traceback.
    pause
)
endlocal
