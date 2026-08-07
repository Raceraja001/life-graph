@echo off
REM -------------------------------------------------
REM Clickable batch file – starts keep_awake.py with logging
REM -------------------------------------------------
REM Prerequisites:
REM   1. Python is installed and added to your system PATH
REM   2. The workspace root contains the "scripts" folder
REM   3. You launch this .bat by double‑clicking it
REM -------------------------------------------------

REM Ensure the log directory exists
set "LOG_DIR=%~dp0..\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Run the keep‑alive script:
REM   --interval 30   : heartbeat every 30 seconds (adjust if you wish)
REM   --log <file>    : write heartbeats to a rotating log file
python scripts/keep_awake.py --interval 30 --log "%LOG_DIR%\keepalive.log"

REM Keep the window open so you can see any final message
pause