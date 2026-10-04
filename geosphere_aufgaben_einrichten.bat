@echo off
rem ======================================================================
rem  Windows-Aufgabenplanung fuer die GeoSphere-Skripte einrichten (PC2).
rem   - Wetter:     stuendlich um xx:05 -> Bulletin an WX   (Replace, Valid 2h)
rem   - Warnungen:  alle 15 Minuten     -> Bulletin an WARN (nur bei Aenderung)
rem  Die Dateien landen in eingang\, TinyBox macht Bulletins daraus,
rem  brocast sendet sie. Fehler stehen in logs\geosphere.log.
rem  Laeuft unter dem angemeldeten Benutzer, ohne Konsolenfenster (pyw).
rem  Entfernen: geosphere_aufgaben_entfernen.bat
rem ======================================================================
cd /d "%~dp0"

set PYW=
for /f "delims=" %%i in ('where pyw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW (
    echo pyw.exe nicht gefunden - ist Python mit dem "py launcher" installiert?
    pause
    exit /b 1
)
echo Python ohne Konsole: %PYW%
if not exist "%~dp0logs" mkdir "%~dp0logs"

schtasks /Create /F /TN "brocast\GeoSphere Wetter" /SC HOURLY /MO 1 /ST 00:05 ^
  /TR "\"%PYW%\" -3 \"%~dp0geosphere_station.py\" --tinybox --log \"%~dp0logs\geosphere.log\""
if errorlevel 1 goto fehler

schtasks /Create /F /TN "brocast\GeoSphere Warnungen" /SC MINUTE /MO 15 ^
  /TR "\"%PYW%\" -3 \"%~dp0geosphere_warnungen.py\" --tinybox --log \"%~dp0logs\geosphere.log\""
if errorlevel 1 goto fehler

echo.
echo Fertig. Die Aufgaben stehen in der Aufgabenplanung unter "brocast".
echo Erster Testlauf jetzt (mit Ausgabe):
py -3 "%~dp0geosphere_station.py" --tinybox --log "%~dp0logs\geosphere.log"
py -3 "%~dp0geosphere_warnungen.py" --tinybox --log "%~dp0logs\geosphere.log"
echo.
echo In eingang\ bzw. eingang\erledigt\ sollte jetzt geosphere_wetter_11334.txt liegen.
echo Meldungen der Skripte: logs\geosphere.log
pause
exit /b 0

:fehler
echo Einrichten fehlgeschlagen (siehe Meldung oben).
pause
exit /b 1
