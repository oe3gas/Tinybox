@echo off
rem dxfeed-Sammler im Dauerbetrieb: nach einem Absturz automatisch neu starten.
rem Verbindungsabbrueche zum Cluster behandelt dxfeed selbst (Neuverbindung).
rem Zum Beenden das Fenster schliessen oder Strg+C und J.
cd /d "%~dp0"
title [dxfeed] DX-Cluster-Sammler
:loop
py -3 -m dxfeed -c dxfeed.conf collect
echo.
echo [dxfeed] %date% %time%  Sammler beendet - Neustart in 30 Sekunden (Strg+C = abbrechen)
timeout /t 30
goto loop
