@echo off
rem TinyBox start menu: update (git pull), then start TBClient / TinyBox / brocast listener.
rem   TinyBox-Start.bat      menu
rem   TinyBox-Start.bat 4    start choice 4 without the menu (e.g. for autostart)
rem Details: INSTALL.md
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0release\start.ps1" -Wahl "%~1"
