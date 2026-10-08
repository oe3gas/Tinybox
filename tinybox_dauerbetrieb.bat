@echo off
rem TinyBox im Dauerbetrieb: nach einem Absturz automatisch neu starten.
rem Hinweis: Auch SHUTDOWN in der Sysop-Konsole fuehrt hier zu einem Neustart.
rem Zum endgueltigen Beenden das Fenster schliessen oder Strg+C und J.
cd /d "%~dp0"
title [tinyb] TinyBox
:loop
py -3 -m tinybox -c tinybox.conf
echo.
echo [tinyb] %date% %time%  TinyBox beendet - Neustart in 15 Sekunden (Strg+C = abbrechen)
timeout /t 15
goto loop
