@echo off
rem ======================================================================
rem  Windows-Aufgabenplanung fuer dxfeed einrichten (PC2), PLANUNG 16c.
rem   - alle 3 Stunden (02:00, 05:00, 08:00 ...): Spots der letzten 24 Stunden
rem     als zwei Bulletins an DX in eingang\ (gleitend, ersetzen sich).
rem   - alle 10 Minuten "dxfeed live": DX jetzt (alle 30 min, nur bei
rem     Aenderung), Baender jetzt (stuendlich), Neu auf dem Band.
rem  Voraussetzung: dxfeed.conf (Rufzeichen eingetragen) und ein laufender
rem  Sammler (start_alles.bat mit START_DXFEED=1 oder dxfeed_dauerbetrieb.bat).
rem  Laeuft unter dem angemeldeten Benutzer, ohne Konsolenfenster (pyw).
rem  Fehler stehen in logs\dxfeed.log. Entfernen: dxfeed_aufgabe_entfernen.bat
rem ======================================================================
cd /d "%~dp0"

if not exist "%~dp0dxfeed.conf" (
    echo dxfeed.conf fehlt: dxfeed.conf.example kopieren und Rufzeichen eintragen.
    pause
    exit /b 1
)

set PYW=
for /f "delims=" %%i in ('where pyw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW (
    echo pyw.exe nicht gefunden - ist Python mit dem "py launcher" installiert?
    pause
    exit /b 1
)
echo Python ohne Konsole: %PYW%
if not exist "%~dp0logs" mkdir "%~dp0logs"

schtasks /Create /F /TN "TinyBox\DX-Zusammenfassung" /SC HOURLY /MO 3 /ST 02:00 ^
  /TR "\"%PYW%\" -3 \"%~dp0dxfeed_start.py\" --log \"%~dp0logs\dxfeed.log\" digest --tinybox"
if errorlevel 1 goto fehler
schtasks /Create /F /TN "TinyBox\DX-Live" /SC MINUTE /MO 10 ^
  /TR "\"%PYW%\" -3 \"%~dp0dxfeed_start.py\" --log \"%~dp0logs\dxfeed.log\" live --tinybox"
if errorlevel 1 goto fehler

echo.
echo Fertig. Die Aufgaben stehen in der Aufgabenplanung unter "TinyBox"
echo (DX-Zusammenfassung alle 3 Stunden, DX-Live alle 10 Minuten).
echo Probelauf jetzt (nur Anzeige, kein Bulletin):
py -3 "%~dp0dxfeed_start.py" digest
pause
exit /b 0

:fehler
echo Einrichten fehlgeschlagen (siehe Meldung oben).
pause
exit /b 1
