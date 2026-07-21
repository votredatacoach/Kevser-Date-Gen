@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0generate.ps1"
if errorlevel 1 pause
