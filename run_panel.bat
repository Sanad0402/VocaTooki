@echo off
REM ============================================================
REM  Voca Tooki - Test Runner launcher
REM  Double-click this file to start the runner panel and open
REM  it in your browser at http://localhost:5000
REM ============================================================
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [ERROR] Virtual environment not found at %PY%
    echo Create it first:  python -m venv .venv ^&^& .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

REM If the panel is already running on port 5000, just open the browser.
netstat -ano | findstr ":5000 " | findstr LISTENING >nul
if %errorlevel%==0 (
    echo Runner already running on http://localhost:5000
) else (
    echo Starting Voca Tooki Test Runner...
    start "Voca Tooki Runner" "%PY%" -u run_panel.py
    REM Give the server a moment to come up before opening the browser.
    timeout /t 3 /nobreak >nul
)

start "" http://localhost:5000/
endlocal
