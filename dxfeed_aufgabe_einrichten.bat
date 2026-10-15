@echo off
rem ======================================================================
rem  Windows-Aufgabenplanung fuer die DX-Zusammenfassung einrichten (PC2).
rem   - taeglich um 05:00 Lokalzeit: Spots der letzten 24 Stunden als
rem     Bulletin an DX in eingang\ (nur lokal, keine @-Adresse).
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

schtasks /Create /F /TN "TinyBox\DX-Zusammenfassung" /SC DAILY /ST 05:00 ^
  /TR "\"%PYW%\" -3 \"%~dp0dxfeed_start.py\" --log \"%~dp0logs\dxfeed.log\" digest --tinybox"
if errorlevel 1 goto fehler

echo.
echo Fertig. Die Aufgabe steht in der Aufgabenplanung unter "TinyBox".
echo Probelauf jetzt (nur Anzeige, kein Bulletin):
py -3 "%~dp0dxfeed_start.py" digest
pause
exit /b 0

:fehler
echo Einrichten fehlgeschlagen (siehe Meldung oben).
pause
exit /b 1
