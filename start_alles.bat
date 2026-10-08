@echo off
rem ======================================================================
rem  Dauerbetrieb PC2: Direwolf, brocastd (Station) und TinyBox starten.
rem  Jedes Programm laeuft in einem eigenen Fenster. Beendet sich brocastd
rem  oder TinyBox unerwartet, wird es nach 15 Sekunden neu gestartet.
rem  Stoppen: im jeweiligen Fenster Strg+C druecken und mit J bestaetigen,
rem  oder das Fenster schliessen.
rem ======================================================================

rem ---- bitte einmal anpassen -------------------------------------------
set START_DIREWOLF=1
set DIREWOLF_DIR=C:\direwolf
set DIREWOLF_CONF=direwolf.conf
rem ----------------------------------------------------------------------

cd /d "%~dp0"
title brocast/TinyBox Starter

if "%START_DIREWOLF%"=="1" (
    if not exist "%DIREWOLF_DIR%\direwolf.exe" (
        echo Direwolf nicht gefunden: %DIREWOLF_DIR%\direwolf.exe
        echo Bitte DIREWOLF_DIR oben in start_alles.bat anpassen.
        pause
        exit /b 1
    )
    echo Starte Direwolf ...
    start "Direwolf" /D "%DIREWOLF_DIR%" direwolf.exe -c "%DIREWOLF_CONF%"
    rem Direwolf braucht ein paar Sekunden, bis KISS- und AGW-Port offen sind
    timeout /t 8 /nobreak >nul
)

echo Starte brocastd ...
start "[brocst] brocastd" /D "%~dp0brocast" cmd /c "%~dp0brocast\brocastd_dauerbetrieb.bat"
timeout /t 3 /nobreak >nul

echo Starte TinyBox ...
start "[tinyb] TinyBox" /D "%~dp0" cmd /c "%~dp0tinybox_dauerbetrieb.bat"

echo Alle Programme gestartet. Dieses Fenster schliesst sich in 10 Sekunden.
timeout /t 10 >nul
