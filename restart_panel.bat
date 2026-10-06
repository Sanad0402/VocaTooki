@echo off
REM ============================================================
REM  Voca Tooki - restart the runner panel
REM  The panel loads the framework ONCE at startup, so after
REM  pulling a fix it has to be restarted. This kills whatever
REM  listens on port 5000 and starts the panel again.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 " ^| findstr LISTENING') do (
    echo Stopping the panel ^(PID %%p^)...
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 2 /nobreak >nul

call run_panel.bat
endlocal
