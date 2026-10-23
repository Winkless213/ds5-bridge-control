@echo off
cd /d "%~dp0"
if exist "dist\DSE Control\DSE Control.exe" (
  start "" "dist\DSE Control\DSE Control.exe"
) else (
  start "" pythonw app.py
)
