@echo off
cd /d "%~dp0"
python setex_monitor.py
if errorlevel 1 pause
