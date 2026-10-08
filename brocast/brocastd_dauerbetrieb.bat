@echo off
rem brocastd im Dauerbetrieb: nach einem Absturz automatisch neu starten.
rem Logs: logs\brocastd_log_*.log, Sendeprotokoll: logs\Sendeprotokoll_*.txt
cd /d "%~dp0"
title [brocst] brocastd
:loop
py -3 -m brocast.daemon -c brocastd.conf
echo.
echo [brocst] %date% %time%  brocastd beendet - Neustart in 15 Sekunden (Strg+C = abbrechen)
timeout /t 15
goto loop
