@echo off
rem ======================================================================
rem  Windows-Aufgabenplanung fuer die GeoSphere-Skripte einrichten (PC2).
rem   - Wetter:     stuendlich um xx:05 -> 24 Stationen Wein-/Waldviertel als
rem                 Einzelberichte (Text + brocast-Wetterseite typ wx, je 1 Frame)
rem                 + Gesamtueberblick (Text + brocast-Tabellenseite, ~5 Frames)
rem                 an WX (Replace, Valid 2h). Nicht --einzel-ohne-brocast: die
rem                 TinyBox sendet jedes Bulletin, ohne Wetterseite ginge der
rem                 (groessere) Text ueber Funk und der Listener zeigt nur Text.
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

rem TLS-Pruefung (seit 20.10.2026 ein): truststore nutzt die Windows-Zertifikatspruefung
py -3 -c "import truststore" >nul 2>nul
if errorlevel 1 (
    echo Installiere truststore fuer die Zertifikatspruefung ...
    py -3 -m pip install --user truststore
)

schtasks /Create /F /TN "brocast\GeoSphere Wetter" /SC HOURLY /MO 1 /ST 00:05 ^
  /TR "\"%PYW%\" -3 \"%~dp0geosphere_station.py\" --region --tinybox --log \"%~dp0logs\geosphere.log\""
if errorlevel 1 goto fehler

schtasks /Create /F /TN "brocast\GeoSphere Warnungen" /SC MINUTE /MO 15 ^
  /TR "\"%PYW%\" -3 \"%~dp0geosphere_warnungen.py\" --tinybox --log \"%~dp0logs\geosphere.log\""
if errorlevel 1 goto fehler

echo.
echo Fertig. Die Aufgaben stehen in der Aufgabenplanung unter "brocast".
echo Erster Testlauf jetzt (mit Ausgabe):
py -3 "%~dp0geosphere_station.py" --region --tinybox --log "%~dp0logs\geosphere.log"
py -3 "%~dp0geosphere_warnungen.py" --tinybox --log "%~dp0logs\geosphere.log"
echo.
echo In eingang\erledigt\ sollten jetzt geosphere_wetter_region.txt und 24 x geosphere_wetter_^<ID^>.txt liegen.
echo Meldungen der Skripte: logs\geosphere.log
pause
exit /b 0

:fehler
echo Einrichten fehlgeschlagen (siehe Meldung oben).
pause
exit /b 1
