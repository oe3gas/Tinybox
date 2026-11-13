@echo off
rem TinyBox installation - start this file from the UNPACKED release ZIP.
rem It copies TinyBox into a folder of your choice, installs Git and Python
rem if missing, and asks for the settings (callsign, Direwolf ...).
cd /d "%~dp0"
if not exist "%~dp0payload\release\install.ps1" (
    echo Bitte die ZIP-Datei zuerst ganz entpacken und install.bat dann
    echo aus dem entpackten Ordner starten.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0payload\release\install.ps1" -Source "%~dp0."
