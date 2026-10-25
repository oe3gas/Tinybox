@echo off
rem ======================================================================
rem  Abholung vom Feeder-Pi einrichten - auf dem PC, auf dem die TinyBox laeuft.
rem   - alle 5 Minuten: fertige Bulletins (dxfeed, GeoSphere) vom Pi holen
rem     und in den TinyBox-Eingang legen (pi_abholung.py, ohne Konsolenfenster)
rem   - auf Wunsch: die bisherigen GeoSphere-/dxfeed-Aufgaben dieses PCs
rem     abschalten, sonst kommen die Bulletins doppelt
rem  Voraussetzung: Pi mit feederpi/install.sh eingerichtet (feederpi\README.md).
rem  Fehler stehen in logs\pi_abholung.log. Entfernen: pi_abholung_entfernen.bat
rem ======================================================================
cd /d "%~dp0"
title [feederpi] Abholung einrichten

set PYW=
for /f "delims=" %%i in ('where pyw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW (
    echo pyw.exe nicht gefunden - ist Python mit dem "py launcher" installiert?
    pause
    exit /b 1
)
if not exist "%~dp0logs" mkdir "%~dp0logs"

set PI_HOST=
set /p PI_HOST=IP-Adresse oder Name des Feeder-Pi (z. B. 10.0.0.20): 
if "%PI_HOST%"=="" (
    echo Abgebrochen.
    pause
    exit /b 1
)

py -3 -c "import pi_abholung as p; p.schluessel_sicherstellen()"
if errorlevel 1 goto fehler

echo.
echo Verbindungstest (beim ersten Mal merkt sich der PC den Schluessel des Pi):
py -3 "%~dp0pi_abholung.py" --host %PI_HOST% --test
if errorlevel 1 (
    echo.
    echo Keine Verbindung. Laeuft der Pi, ist install.sh durch, und stand beim
    echo Vorbereiten der SD-Karte schon dieser PC-Schluessel als abholung.pub drauf?
    goto fehler
)

schtasks /Create /F /TN "TinyBox\Pi-Abholung" /SC MINUTE /MO 5 ^
  /TR "\"%PYW%\" -3 \"%~dp0pi_abholung.py\" --host %PI_HOST% --log \"%~dp0logs\pi_abholung.log\""
if errorlevel 1 goto fehler
echo Aufgabe "TinyBox\Pi-Abholung" angelegt (alle 5 Minuten).

echo.
echo Bisher erzeugt dieser PC die Bulletins selbst. Laufen beide, kommen sie doppelt.
choice /C JN /M "Aufgaben GeoSphere und DX-Zusammenfassung hier entfernen und den dxfeed-Sammler abschalten"
if errorlevel 2 goto ende
schtasks /Delete /F /TN "brocast\GeoSphere Wetter" 2>nul
schtasks /Delete /F /TN "brocast\GeoSphere Warnungen" 2>nul
schtasks /Delete /F /TN "brocast\GeoSphere Prognose" 2>nul
schtasks /Delete /F /TN "TinyBox\DX-Zusammenfassung" 2>nul
schtasks /Delete /F /TN "TinyBox\DX-Live" 2>nul
rem start_alles.bat startet den Sammler nur, wenn dxfeed.conf da ist
if exist "%~dp0dxfeed.conf" (
    move /Y "%~dp0dxfeed.conf" "%~dp0dxfeed.conf.vor-feederpi" >nul
    echo dxfeed.conf umbenannt in dxfeed.conf.vor-feederpi - start_alles.bat startet den Sammler nicht mehr.
)
echo Ein noch offenes Fenster "[dxfeed] DX-Cluster-Sammler" bitte schliessen.

:ende
echo.
echo Fertig. Protokoll: logs\pi_abholung.log
pause
exit /b 0

:fehler
echo Einrichten fehlgeschlagen (siehe Meldung oben).
pause
exit /b 1
