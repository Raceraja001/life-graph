@echo off
REM Scheduled runner for the Life Graph transcript uploader.
REM Register with Task Scheduler to run every 15 minutes.
"C:\Python314\python.exe" "%~dp0transcript_uploader.py" >> "%USERPROFILE%\.life_graph_uploader.log" 2>&1
